"""
pre_image_cache.py — Auto-fetch and cache baseline (pre-disaster) satellite imagery.

Uses ESRI World Imagery tiles (free, no API key) to download a stitched satellite
mosaic for any lat/lng bounding box. The stitched image is stored locally so it
never needs to be re-fetched on subsequent requests.

Cache location: backend/cache/pre_imagery/<lat>_<lng>_<radius_km>.jpg
"""

import io
import logging
import math
import hashlib
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "pre_imagery"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ESRI World Imagery — free, no API key, high resolution globally
ESRI_TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


def _deg2tile(lat: float, lng: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lng to tile (x, y) at given zoom level."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lng + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _tile2deg(x: int, y: int, zoom: int) -> tuple[float, float]:
    """Convert tile (x, y) back to top-left lat/lng."""
    n = 2 ** zoom
    lng = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lng


def _cache_key(lat: float, lng: float, radius_km: float) -> str:
    raw = f"{round(lat, 4)}_{round(lng, 4)}_{round(radius_km, 2)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def fetch_pre_image(lat: float, lng: float, radius_km: float, zoom: int = 15) -> Optional[bytes]:
    """
    Returns JPEG bytes of a stitched satellite tile mosaic for the given area.

    Checks local cache first. If not cached, fetches tiles from ESRI World Imagery,
    stitches them into one image, and caches to disk.

    Args:
        lat, lng: Center of area
        radius_km: Approximate radius to cover
        zoom: Tile zoom level (13=regional, 15=building-level, 17=rooftop)

    Returns:
        JPEG bytes of the pre-disaster baseline image, or None on failure.
    """
    key = _cache_key(lat, lng, radius_km)
    cache_path = CACHE_DIR / f"{key}.jpg"

    # --- Cache hit ---
    if cache_path.exists():
        logger.info(f"[PreImageCache] Cache hit → {cache_path.name}")
        return cache_path.read_bytes()

    # --- Cache miss: fetch from ESRI ---
    logger.info(f"[PreImageCache] Cache miss — fetching ESRI tiles for ({lat:.4f}, {lng:.4f}) r={radius_km}km z={zoom}")
    try:
        import requests
        from PIL import Image

        # Calculate which tiles cover the bounding box
        delta_lat = radius_km / 111.0
        delta_lng = radius_km / (111.0 * abs(math.cos(math.radians(lat))) + 1e-9)

        min_lat = lat - delta_lat
        max_lat = lat + delta_lat
        min_lng = lng - delta_lng
        max_lng = lng + delta_lng

        # Get tile range
        tile_x_min, tile_y_max = _deg2tile(min_lat, min_lng, zoom)
        tile_x_max, tile_y_min = _deg2tile(max_lat, max_lng, zoom)

        # Clamp to a reasonable 4x4 tile max to avoid massive downloads
        tile_x_min = max(tile_x_min, tile_x_max - 3)
        tile_y_min = max(tile_y_min, tile_y_max - 3)
        tile_x_max = min(tile_x_max, tile_x_min + 3)
        tile_y_max = min(tile_y_max, tile_y_min + 3)

        n_x = tile_x_max - tile_x_min + 1
        n_y = tile_y_max - tile_y_min + 1
        TILE_SIZE = 256

        mosaic = Image.new("RGB", (n_x * TILE_SIZE, n_y * TILE_SIZE))

        headers = {"User-Agent": "DISHA-DisasterResponseAI/1.0"}

        for yi, ty in enumerate(range(tile_y_min, tile_y_max + 1)):
            for xi, tx in enumerate(range(tile_x_min, tile_x_max + 1)):
                url = ESRI_TILE_URL.format(z=zoom, y=ty, x=tx)
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        tile_img = Image.open(io.BytesIO(r.content)).convert("RGB")
                        mosaic.paste(tile_img, (xi * TILE_SIZE, yi * TILE_SIZE))
                    else:
                        logger.warning(f"[PreImageCache] Tile {tx}/{ty} returned {r.status_code}")
                except Exception as te:
                    logger.warning(f"[PreImageCache] Tile {tx}/{ty} fetch failed: {te}")

        # Save to cache
        buf = io.BytesIO()
        mosaic.save(buf, format="JPEG", quality=90)
        image_bytes = buf.getvalue()
        cache_path.write_bytes(image_bytes)
        logger.info(f"[PreImageCache] Cached {n_x*n_y} tiles → {cache_path.name} ({len(image_bytes)//1024}KB)")
        return image_bytes

    except Exception as e:
        logger.error(f"[PreImageCache] Failed to fetch pre-image: {e}")
        return None
