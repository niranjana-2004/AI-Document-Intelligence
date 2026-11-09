"""
Cognidocs Layout Visualizer 4.0

Generates visual layout debug and inspection artifacts for handwritten pages.
Supports detailed bounding-box overlays with confidence labels and simplified semantic region maps.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Category Color Palette (BGR)
COLOR_TEXT = (46, 139, 87)         # Sea Green
COLOR_HEADING = (218, 112, 37)      # Steel Blue / Cyan
COLOR_DIAGRAM = (30, 105, 237)      # Amber / Orange
COLOR_FORMULA = (180, 0, 180)       # Purple
COLOR_TABLE = (205, 179, 0)         # Cyan / Gold
COLOR_ARROW = (0, 0, 220)           # Red
COLOR_BOX = (0, 215, 255)           # Yellow
COLOR_BACKGROUND = (128, 128, 128)  # Gray
COLOR_UNKNOWN = (200, 0, 200)       # Magenta

REGION_COLORS = {
    "text": COLOR_TEXT,
    "heading": COLOR_HEADING,
    "diagram": COLOR_DIAGRAM,
    "formula": COLOR_FORMULA,
    "table": COLOR_TABLE,
    "arrow_connector": COLOR_ARROW,
    "box_border": COLOR_BOX,
    "background": COLOR_BACKGROUND,
    "unknown": COLOR_UNKNOWN
}


def render_detailed_layout(
    image: np.ndarray,
    regions: List[Dict[str, Any]],
    output_path: Path
) -> None:
    """
    Render detailed visual overlay showing bounding boxes, category labels,
    confidence scores, and polygon contours on top of the original image.
    """
    canvas = image.copy()
    h, w = canvas.shape[:2]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for reg in regions:
        rtype = reg.get("region_type", "unknown").lower()
        color = REGION_COLORS.get(rtype, (0, 255, 0))
        bbox = reg.get("bbox", [0, 0, 0, 0])
        x, y, bw, bh = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        conf = float(reg.get("confidence", 0.0))

        # Clamp to image bounds
        x1 = max(0, min(w - 1, x))
        y1 = max(0, min(h - 1, y))
        x2 = max(0, min(w, x + bw))
        y2 = max(0, min(h, y + bh))

        if x2 <= x1 or y2 <= y1:
            continue

        # Draw bounding rectangle
        thickness = 2 if rtype in ("diagram", "table") else 2
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)

        # Draw polygon contour if present
        poly = reg.get("polygon")
        if poly and len(poly) >= 3:
            pts = np.array(poly, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(canvas, [pts], isClosed=True, color=color, thickness=2)

        # Draw label banner
        label = f"{rtype.upper()} ({int(conf * 100)}%)"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        (label_w, label_h), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)

        banner_y1 = max(0, y1 - label_h - 6)
        banner_y2 = y1
        banner_x2 = min(w, x1 + label_w + 10)

        # Filled banner background
        cv2.rectangle(canvas, (x1, banner_y1), (banner_x2, banner_y2), color, -1)
        # White label text
        cv2.putText(
            canvas,
            label,
            (x1 + 4, y1 - 4),
            font,
            font_scale,
            (255, 255, 255),
            font_thickness,
            cv2.LINE_AA
        )

    # Save output
    suffix = output_path.suffix.lower() or ".png"
    success, encoded = cv2.imencode(suffix, canvas)
    if success:
        encoded.tofile(str(output_path))
    else:
        cv2.imwrite(str(output_path), canvas)


def render_simplified_layout(
    image: np.ndarray,
    regions: List[Dict[str, Any]],
    output_path: Path
) -> None:
    """
    Render high-contrast simplified semantic layout map showing primary
    content blocks (TEXT, HEADING, DIAGRAM, FORMULA, TABLE) with semi-transparent tint.
    """
    h, w = image.shape[:2]
    overlay = image.copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for reg in regions:
        rtype = reg.get("region_type", "unknown").lower()
        if rtype not in ("text", "heading", "diagram", "formula", "table"):
            continue

        color = REGION_COLORS.get(rtype, (0, 255, 0))
        bbox = reg.get("bbox", [0, 0, 0, 0])
        x, y, bw, bh = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

        x1 = max(0, min(w - 1, x))
        y1 = max(0, min(h - 1, y))
        x2 = max(0, min(w, x + bw))
        y2 = max(0, min(h, y + bh))

        if x2 <= x1 or y2 <= y1:
            continue

        # Tint the block with semi-transparent color
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        # Draw solid border
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 3)

    # Alpha blend: 65% original + 35% overlay tint
    alpha = 0.35
    simplified = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)

    # Add region label watermarks in center of each block
    for reg in regions:
        rtype = reg.get("region_type", "unknown").lower()
        if rtype not in ("text", "heading", "diagram", "formula", "table"):
            continue
        bbox = reg.get("bbox", [0, 0, 0, 0])
        x, y, bw, bh = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        label = rtype.upper()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        font_thickness = 2
        (label_w, label_h), _ = cv2.getTextSize(label, font, font_scale, font_thickness)
        cx = x + (bw - label_w) // 2
        cy = y + (bh + label_h) // 2

        if 0 <= cx < w and 0 <= cy < h:
            cv2.rectangle(simplified, (cx - 6, cy - label_h - 6), (cx + label_w + 6, cy + 6), (0, 0, 0), -1)
            cv2.putText(simplified, label, (cx, cy), font, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)

    suffix = output_path.suffix.lower() or ".png"
    success, encoded = cv2.imencode(suffix, simplified)
    if success:
        encoded.tofile(str(output_path))
    else:
        cv2.imwrite(str(output_path), simplified)

