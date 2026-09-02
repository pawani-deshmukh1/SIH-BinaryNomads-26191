"""
mask_aggregator.py — Aggregates multi-frame masks into a single union mask.
"""
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def aggregate_masks(masks: list[np.ndarray], confidences: list[float]) -> tuple[Optional[np.ndarray], float]:
    """
    Takes a list of 2D integer masks (from multiple frames) and unions them.
    
    Since binary masks are 0 (no hazard) and 1 (hazard), np.max acts as a union.
    For multi-class (0=none, 1=minor, 2=destroyed), np.max keeps the highest severity.
    
    Args:
        masks: List of 2D numpy arrays.
        confidences: List of model confidences for each frame.
        
    Returns:
        (merged_mask, max_confidence)
    """
    valid_masks = [m for m in masks if m is not None]
    
    if not valid_masks:
        return None, 0.0
        
    try:
        stacked = np.stack(valid_masks, axis=0)
        merged_mask = np.max(stacked, axis=0)
        max_conf = max(confidences, default=0.0)
        return merged_mask, max_conf
    except Exception as e:
        logger.error(f"[MaskAggregator] Failed to aggregate masks: {e}")
        return None, 0.0
