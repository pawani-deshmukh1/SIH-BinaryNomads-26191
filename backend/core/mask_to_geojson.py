"""
mask_to_geojson.py — Convert ONNX model output masks to GeoJSON polygon features.

The models output numpy arrays of shape [H, W] (after argmax/squeeze).
This module converts connected pixel regions into vector polygon GeoJSON,
properly projected from pixel space to WGS84 lat/lng using the image's
known bounding box.
"""
import numpy as np
from typing import Literal
from datetime import datetime, timezone
import json


def _bbox_to_transform(bbox: tuple[float, float, float, float], width: int, height: int):
    """
    Build a simple affine transform mapping pixel (col, row) → (lng, lat).
    bbox: (min_lng, min_lat, max_lng, max_lat)
    """
    min_lng, min_lat, max_lng, max_lat = bbox
    lng_per_pixel = (max_lng - min_lng) / width
    lat_per_pixel = (max_lat - min_lat) / height  # lat increases upward

    def pixel_to_lnglat(col: float, row: float) -> tuple[float, float]:
        lng = min_lng + col * lng_per_pixel
        # row=0 is top of image (max_lat), row=height is bottom (min_lat)
        lat = max_lat - row * lat_per_pixel
        return (lng, lat)

    return pixel_to_lnglat


def mask_to_geojson_features(
    mask: np.ndarray,
    bbox: tuple[float, float, float, float],
    layer_type: str,
    class_labels: dict[int, str],
    confidence: float,
    min_area_pixels: int = 20,
    simplify_tolerance: float = 0.0001,
) -> list[dict]:
    """
    Convert a 2D integer mask to a list of GeoJSON Feature dicts.

    Args:
        mask: np.ndarray shape [H, W], integer class values
        bbox: (min_lng, min_lat, max_lng, max_lat) of the image tile
        layer_type: e.g. "building_damage", "flood_zone", "landslide_zone"
        class_labels: map from integer class value to string label,
                      e.g. {1: "minor", 2: "destroyed"} — class 0 = background, skipped
        confidence: model confidence score (0.0-1.0)
        min_area_pixels: skip regions smaller than this (noise filter)
        simplify_tolerance: polygon simplification in degrees (reduces vertex count)

    Returns:
        List of GeoJSON Feature dicts
    """
    try:
        import rasterio.features
        from shapely.geometry import shape, mapping
        from shapely.ops import unary_union
        import shapely
    except ImportError:
        # Fallback: return bounding box polygon if rasterio/shapely not available
        return _fallback_bbox_feature(bbox, layer_type, list(class_labels.values())[0] if class_labels else "unknown", confidence)

    height, width = mask.shape
    pixel_to_lnglat = _bbox_to_transform(bbox, width, height)

    # Build a rasterio-compatible affine transform
    try:
        from rasterio.transform import from_bounds
        transform = from_bounds(*bbox, width=width, height=height)
    except ImportError:
        return _fallback_bbox_feature(bbox, layer_type, list(class_labels.values())[0] if class_labels else "unknown", confidence)

    features = []
    now = datetime.now(timezone.utc).isoformat()

    for class_val, label in class_labels.items():
        if class_val == 0:
            continue  # skip background

        binary_mask = (mask == class_val).astype(np.uint8)

        if binary_mask.sum() < min_area_pixels:
            continue

        # Extract shapes (connected components → polygons)
        try:
            shapes = list(rasterio.features.shapes(binary_mask, transform=transform))
        except Exception:
            continue

        polygons = []
        for geom_dict, val in shapes:
            if val != 1:
                continue
            try:
                geom = shape(geom_dict)
                if geom.area < 1e-10:
                    continue
                if simplify_tolerance > 0:
                    geom = geom.simplify(simplify_tolerance, preserve_topology=True)
                polygons.append(geom)
            except Exception:
                continue

        if not polygons:
            continue

        # Merge overlapping/adjacent polygons of the same class
        try:
            merged = unary_union(polygons)
        except Exception:
            merged = polygons[0] if polygons else None

        if merged is None or merged.is_empty:
            continue

        # Handle MultiPolygon — emit one feature per polygon
        if merged.geom_type == "MultiPolygon":
            geom_list = list(merged.geoms)
        else:
            geom_list = [merged]

        for geom in geom_list:
            if geom.is_empty:
                continue
            feature = {
                "type": "Feature",
                "properties": {
                    "layer_type": layer_type,
                    "label": label,
                    "confidence": round(confidence, 4),
                    "last_updated": now,
                },
                "geometry": mapping(geom),
            }
            features.append(feature)

    return features


def damage_mask_to_features(
    mask: np.ndarray,
    bbox: tuple[float, float, float, float],
    damage_confidence: float,
) -> list[dict]:
    """
    Convenience wrapper for the 3-class damage model output.
    Classes: 0=no_damage, 1=minor_damage, 2=destroyed
    """
    return mask_to_geojson_features(
        mask=mask,
        bbox=bbox,
        layer_type="damage_zone",
        class_labels={1: "minor_damage", 2: "destroyed"},
        confidence=damage_confidence,
    )


def flood_mask_to_features(
    mask: np.ndarray,
    bbox: tuple[float, float, float, float],
    flood_confidence: float,
) -> list[dict]:
    """
    Convenience wrapper for the binary flood segmentation model.
    Classes: 0=clear, 1=flooded
    """
    return mask_to_geojson_features(
        mask=mask,
        bbox=bbox,
        layer_type="flood_zone",
        class_labels={1: "flooded"},
        confidence=flood_confidence,
    )


def landslide_mask_to_features(
    mask: np.ndarray,
    bbox: tuple[float, float, float, float],
    landslide_confidence: float,
) -> list[dict]:
    """
    Convenience wrapper for the binary landslide segmentation model.
    Classes: 0=clear, 1=landslide_hazard
    """
    return mask_to_geojson_features(
        mask=mask,
        bbox=bbox,
        layer_type="landslide_zone",
        class_labels={1: "landslide_hazard"},
        confidence=landslide_confidence,
    )


def _fallback_bbox_feature(
    bbox: tuple,
    layer_type: str,
    label: str,
    confidence: float,
) -> list[dict]:
    """Fallback: return the full bbox as a polygon if shapely/rasterio unavailable."""
    min_lng, min_lat, max_lng, max_lat = bbox
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "type": "Feature",
        "properties": {
            "layer_type": layer_type,
            "label": label,
            "confidence": round(confidence, 4),
            "last_updated": now,
            "_note": "fallback_bbox — rasterio/shapely unavailable",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [min_lng, min_lat],
                [max_lng, min_lat],
                [max_lng, max_lat],
                [min_lng, max_lat],
                [min_lng, min_lat],
            ]],
        },
    }]
