import logging
from typing import List, Dict, Any, Tuple
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class LineCrop:
    def __init__(self, line_index: int, image: Image.Image, bbox: Tuple[int, int, int, int]):
        self.line_index = line_index
        self.image = image
        self.bbox = bbox  # (x, y, w, h)


def segment_page_into_lines(
    color_or_gray_image: np.ndarray,
    min_line_height: int = 15,
    padding: int = 8
) -> Tuple[List[LineCrop], bool]:
    """
    Segment a handwritten page into horizontal text line crops using morphological analysis.

    Args:
        color_or_gray_image: Input numpy image array (BGR or Grayscale).
        min_line_height: Minimum pixel height for a valid text line.
        padding: Pixel padding added around each detected text line box.

    Returns:
        (line_crops, is_empty_page)
    """
    if len(color_or_gray_image.shape) == 3:
        gray = cv2.cvtColor(color_or_gray_image, cv2.COLOR_BGR2GRAY)
        bgr = color_or_gray_image
    else:
        gray = color_or_gray_image
        bgr = cv2.cvtColor(color_or_gray_image, cv2.COLOR_GRAY2BGR)

    h, w = gray.shape[:2]

    # Guard: if image is virtually uniform / blank paper with no variance
    if float(np.std(gray)) < 3.0:
        logger.info("Page detected as empty or blank (near-zero grayscale variance)")
        return [], True

    # Invert threshold: text ink is white (255), background paper is black (0)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    ink_pixel_count = cv2.countNonZero(thresh)
    total_pixels = h * w
    ink_ratio = ink_pixel_count / total_pixels

    # Empty page detection: less than 0.05% non-background pixels
    if ink_ratio < 0.0005:
        logger.info("Page detected as empty or blank (ink ratio < 0.05%)")
        return [], True

    # Horizontal dilation: merge words on the same line into unified line strips
    # Use adaptive kernel width relative to page width
    kernel_width = max(25, int(w * 0.035))
    kernel_height = max(2, int(h * 0.003))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, kernel_height))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    # Find bounding contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    raw_boxes = []
    min_width = max(30, int(w * 0.04))

    for c in contours:
        x, y, box_w, box_h = cv2.boundingRect(c)
        if box_h >= min_line_height and box_w >= min_width:
            raw_boxes.append((x, y, box_w, box_h))

    # Fallback if morphological dilation found no distinct lines but ink exists
    if not raw_boxes:
        # Find non-zero bounding rect of the whole ink area
        x, y, box_w, box_h = cv2.boundingRect(thresh)
        if box_w > 10 and box_h > 10:
            raw_boxes.append((x, y, box_w, box_h))
        else:
            return [], True

    # Sort bounding boxes in natural reading order: top-to-bottom
    # Group boxes that have substantial vertical overlap
    sorted_by_y = sorted(raw_boxes, key=lambda b: b[1])

    merged_lines = []
    for box in sorted_by_y:
        x, y, box_w, box_h = box
        matched = False
        for idx, line in enumerate(merged_lines):
            lx, ly, lw, lh = line
            # Check if this box overlaps vertically with existing line
            overlap = min(y + box_h, ly + lh) - max(y, ly)
            min_h = min(box_h, lh)
            if min_h > 0 and (overlap / min_h) > 0.45:
                # Merge boxes on the same line
                new_x = min(x, lx)
                new_y = min(y, ly)
                new_w = max(x + box_w, lx + lw) - new_x
                new_h = max(y + box_h, ly + lh) - new_y
                merged_lines[idx] = (new_x, new_y, new_w, new_h)
                matched = True
                break
        if not matched:
            merged_lines.append(box)

    # Final sort top-to-bottom
    merged_lines.sort(key=lambda b: b[1])

    line_crops: List[LineCrop] = []
    pil_image_full = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))

    for idx, (bx, by, bw, bh) in enumerate(merged_lines):
        # Apply padding clamped to image bounds
        crop_x1 = max(0, bx - padding)
        crop_y1 = max(0, by - padding)
        crop_x2 = min(w, bx + bw + padding)
        crop_y2 = min(h, by + bh + padding)

        cropped_pil = pil_image_full.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        line_crops.append(LineCrop(
            line_index=idx + 1,
            image=cropped_pil,
            bbox=(crop_x1, crop_y1, crop_x2 - crop_x1, crop_y2 - crop_y1)
        ))

    logger.info(f"Segmented page into {len(line_crops)} text line crops.")
    return line_crops, False
