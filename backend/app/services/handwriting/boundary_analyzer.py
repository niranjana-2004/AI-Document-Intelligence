"""
Boundary Analyzer Service for Cognidocs OCR 3.5.
Provides visual word-boundary analysis on text line images:
- Adaptive scale estimation (character width, stroke width, inter-token spacing)
- Merged word detection and ink-valley split validation
- Erroneously split word detection and bounding-box gap analysis
- Continuous boundary confidence scoring grounded strictly in image metrics
"""

import logging
import math
import re
from typing import Dict, List, Any, Tuple, Optional, Set
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def estimate_line_spacing_statistics(
    line_crop_bgr: np.ndarray,
    tokens: List[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Compute adaptive line-level spacing statistics from the line image and token bounding boxes.
    Adapts dynamically to the writing scale of the specific line rather than using fixed pixel thresholds.
    """
    if line_crop_bgr is None or line_crop_bgr.size == 0:
        return {"scale_px": 25.0, "median_gap": 15.0, "mean_char_w": 18.0}

    h, w = line_crop_bgr.shape[:2]
    gray = cv2.cvtColor(line_crop_bgr, cv2.COLOR_BGR2GRAY) if len(line_crop_bgr.shape) == 3 else line_crop_bgr
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Suppress ruling lines
    k_len = max(15, int(w * 0.08))
    ruling = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k_len, 1)))
    clean_thresh = cv2.subtract(thresh, ruling)

    # Horizontal projection
    col_ink = np.sum(clean_thresh > 0, axis=0)
    active_cols = np.where(col_ink > 2)[0]

    total_ink_width = (active_cols[-1] - active_cols[0]) if len(active_cols) > 1 else w
    total_chars = max(1, sum(len(t.get("token_text", "")) for t in tokens)) if tokens else 25

    mean_char_w = max(8.0, min(60.0, float(total_ink_width) / float(total_chars)))

    # Compute gaps between consecutive token local bboxes
    gaps = []
    if tokens and len(tokens) > 1:
        for i in range(len(tokens) - 1):
            curr_box = tokens[i].get("local_bbox") or tokens[i].get("token_bbox")
            next_box = tokens[i + 1].get("local_bbox") or tokens[i + 1].get("token_bbox")
            if curr_box and next_box:
                curr_right = curr_box[0] + curr_box[2]
                next_left = next_box[0]
                gap = next_left - curr_right
                if gap > 0:
                    gaps.append(float(gap))

    median_gap = float(np.median(gaps)) if gaps else (mean_char_w * 0.85)

    return {
        "line_height": float(h),
        "total_ink_width": float(total_ink_width),
        "mean_char_w": round(mean_char_w, 2),
        "median_gap": round(median_gap, 2),
        "scale_px": round(mean_char_w * 1.2, 2)
    }


def find_ink_valleys_in_token(
    token_crop_bgr: np.ndarray,
    min_valley_width: int = 4
) -> List[Dict[str, Any]]:
    """
    Find internal whitespace dips / ink valleys in a cropped token image where
    ink density drops below threshold, indicating a physical inter-word gap.
    """
    if token_crop_bgr is None or token_crop_bgr.size == 0:
        return []

    h, w = token_crop_bgr.shape[:2]
    if w < 30:
        return []

    gray = cv2.cvtColor(token_crop_bgr, cv2.COLOR_BGR2GRAY) if len(token_crop_bgr.shape) == 3 else token_crop_bgr
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    col_ink = np.sum(thresh > 0, axis=0)
    max_ink = max(1.0, float(np.max(col_ink)))
    norm_ink = col_ink / max_ink

    # Look for valleys in the middle 70% of the token width
    search_start = max(5, int(w * 0.15))
    search_end = min(w - 5, int(w * 0.85))

    valleys = []
    in_valley = False
    v_start = 0

    for col in range(search_start, search_end):
        if norm_ink[col] < 0.12:  # very low ink density
            if not in_valley:
                in_valley = True
                v_start = col
        else:
            if in_valley:
                in_valley = False
                v_width = col - v_start
                if v_width >= min_valley_width:
                    mid_col = (v_start + col) // 2
                    min_val = float(np.min(norm_ink[v_start:col]))
                    valleys.append({
                        "col": mid_col,
                        "width": v_width,
                        "min_density": round(min_val, 3),
                        "relative_pos": round(float(mid_col) / float(w), 3)
                    })

    return valleys


def evaluate_split_boundary_evidence(
    token_crop_bgr: np.ndarray,
    split_char_index: int,
    total_token_chars: int,
    line_scale: Dict[str, float]
) -> Dict[str, Any]:
    """
    Evaluate physical whitespace evidence for splitting a token at a proposed character split.
    Checks if an ink valley or whitespace gap exists at the proportional horizontal column.
    """
    if token_crop_bgr is None or token_crop_bgr.size == 0 or total_token_chars <= 1:
        return {"has_visual_gap": False, "boundary_score": 0.0, "split_col": 0}

    h, w = token_crop_bgr.shape[:2]
    expected_ratio = float(split_char_index) / float(total_token_chars)
    expected_col = int(w * expected_ratio)

    valleys = find_ink_valleys_in_token(token_crop_bgr, min_valley_width=3)

    if not valleys:
        # Check local column ink around expected_col
        search_window = max(6, int(line_scale.get("mean_char_w", 18.0) * 0.6))
        c_min = max(0, expected_col - search_window)
        c_max = min(w, expected_col + search_window)

        gray = cv2.cvtColor(token_crop_bgr, cv2.COLOR_BGR2GRAY) if len(token_crop_bgr.shape) == 3 else token_crop_bgr
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        col_ink = np.sum(thresh > 0, axis=0)

        if c_max > c_min:
            min_ink_col = c_min + int(np.argmin(col_ink[c_min:c_max]))
            local_min_ink = col_ink[min_ink_col]
            avg_ink = float(np.mean(col_ink)) if np.mean(col_ink) > 0 else 1.0
            dip_ratio = 1.0 - (float(local_min_ink) / avg_ink) if avg_ink > 0 else 0.0

            if dip_ratio >= 0.50:
                score = round(min(0.95, max(0.50, 0.50 + dip_ratio * 0.40)), 2)
                return {
                    "has_visual_gap": True,
                    "boundary_score": score,
                    "split_col": min_ink_col,
                    "dip_ratio": round(dip_ratio, 2)
                }

        return {"has_visual_gap": False, "boundary_score": 0.20, "split_col": expected_col}

    # Find the valley closest to expected_col
    best_v = min(valleys, key=lambda v: abs(v["col"] - expected_col))
    dist = abs(best_v["col"] - expected_col)
    tolerance = max(8, int(line_scale.get("mean_char_w", 18.0) * 0.75))

    if dist <= tolerance:
        depth_bonus = (1.0 - best_v["min_density"]) * 0.25
        width_bonus = min(0.15, (best_v["width"] / line_scale.get("mean_char_w", 18.0)) * 0.15)
        score = round(min(0.98, max(0.65, 0.60 + depth_bonus + width_bonus)), 2)
        return {
            "has_visual_gap": True,
            "boundary_score": score,
            "split_col": best_v["col"],
            "valley_width": best_v["width"],
            "depth": round(1.0 - best_v["min_density"], 2)
        }

    return {"has_visual_gap": False, "boundary_score": 0.35, "split_col": expected_col}


def evaluate_merge_boundary_evidence(
    box1: List[int],
    box2: List[int],
    line_scale: Dict[str, float]
) -> Dict[str, Any]:
    """
    Evaluate physical whitespace evidence for merging two adjacent tokens into a single word.
    If the horizontal gap between box1 and box2 is unusually narrow relative to the line's
    median inter-word gap, the physical layout strongly supports a single continuous word.
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    gap_px = float(x2 - (x1 + w1))
    median_gap = max(8.0, line_scale.get("median_gap", 15.0))
    mean_char_w = max(8.0, line_scale.get("mean_char_w", 18.0))

    # Gap ratio relative to median inter-word gap
    gap_ratio = gap_px / median_gap if median_gap > 0 else 1.0

    if gap_px <= 0:
        # Overlapping or touching bounding boxes
        score = 0.95
        has_narrow_gap = True
    elif gap_px < (median_gap * 0.50):
        # Gap is less than half the median inter-word gap
        score = round(0.90 - (gap_ratio * 0.20), 2)
        has_narrow_gap = True
    elif gap_px < (median_gap * 0.85):
        # Slightly narrow gap
        score = round(0.70 - (gap_ratio * 0.15), 2)
        has_narrow_gap = True
    else:
        # Standard or wide gap indicates two distinct handwritten words
        score = round(max(0.10, 0.50 - (gap_ratio * 0.20)), 2)
        has_narrow_gap = False

    return {
        "gap_px": round(gap_px, 1),
        "gap_ratio": round(gap_ratio, 2),
        "has_narrow_gap": has_narrow_gap,
        "boundary_score": score
    }

