import logging
from typing import List, Tuple
import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

logger = logging.getLogger(__name__)


class LineCrop:
    def __init__(self, line_index: int, image: Image.Image, bbox: Tuple[int, int, int, int]):
        self.line_index = line_index
        self.image = image
        self.bbox = bbox  # (x, y, w, h)


def segment_page_into_lines(
    color_or_gray_image: np.ndarray,
    min_line_height: int = 15,
    padding: int = 6
) -> Tuple[List[LineCrop], bool]:
    """
    Segment a handwritten document page into individual text line crops using
    smoothed horizontal projection profile analysis with local minima valley detection.

    Handles ascender/descender vertical overlap and preserves natural reading order.

    Args:
        color_or_gray_image: Input numpy image array (BGR or Grayscale).
        min_line_height: Minimum pixel height for a valid text line.
        padding: Pixel padding added around detected text lines.

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

    # 1. Blank page detection via standard deviation
    if float(np.std(gray)) < 3.0:
        logger.info("Page detected as empty or blank (near-zero grayscale variance)")
        return [], True

    # 2. Otsu thresholding for ink vs background
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    ink_pixel_count = cv2.countNonZero(thresh)
    total_pixels = h * w
    ink_ratio = ink_pixel_count / total_pixels

    if ink_ratio < 0.0005:
        logger.info("Page detected as empty or blank (ink ratio < 0.05%)")
        return [], True

    # 3. Horizontal Projection Profile & Valley Finding
    row_ink = np.sum(thresh > 0, axis=1).astype(np.float32)
    # Adaptive Gaussian smoothing parameter based on page height
    sigma = max(8.0, min(14.0, h / 100.0))
    smoothed = gaussian_filter1d(row_ink, sigma=sigma)

    # Minimum line distance (~2.0% of page height) and prominence threshold
    min_dist = max(22, int(h * 0.02))
    prominence = max(15.0, float(np.percentile(smoothed, 50) * 0.3))
    peaks, _ = find_peaks(smoothed, distance=min_dist, prominence=prominence)

    strips = []
    pil_image_full = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))

    if len(peaks) >= 1:
        # Determine top boundary
        first_ink = np.where(row_ink[:peaks[0]] > 5)[0]
        top_y = max(0, first_ink[0] - padding) if len(first_ink) > 0 else max(0, int(peaks[0] - (min_dist * 1.5)))

        valleys = [top_y]
        for i in range(len(peaks) - 1):
            p1 = peaks[i]
            p2 = peaks[i + 1]
            # Valley is the local minimum ink row between two consecutive text line peaks
            valley_y = p1 + int(np.argmin(smoothed[p1:p2]))
            valleys.append(valley_y)

        # Determine bottom boundary
        last_ink = np.where(row_ink[peaks[-1]:] > 5)[0]
        bottom_y = min(h, peaks[-1] + last_ink[-1] + padding) if len(last_ink) > 0 else min(h, int(peaks[-1] + (min_dist * 1.5)))
        valleys.append(bottom_y)

        for i in range(len(valleys) - 1):
            y1 = max(0, valleys[i])
            y2 = min(h, valleys[i + 1])
            if y2 - y1 < min_line_height:
                continue

            # Detect horizontal word bounds in this strip
            strip_thresh = thresh[y1:y2, :]
            col_sums = np.sum(strip_thresh > 0, axis=0)
            cols = np.where(col_sums > 2)[0]
            if len(cols) > 0:
                x1 = max(0, int(cols[0]) - padding * 2)
                x2 = min(w, int(cols[-1]) + padding * 2)
            else:
                x1, x2 = 0, w

            box_w = max(10, x2 - x1)
            box_h = y2 - y1

            # Quality Check 1: Reject empty notebook ruling lines or blank margins
            strip_ink = np.sum(strip_thresh > 0)
            strip_area = box_w * box_h
            ink_density = (strip_ink / strip_area) if strip_area > 0 else 0.0

            # Check for printed horizontal notebook ruling lines (thin horizontal line across entire page)
            strip_row_ink = np.sum(strip_thresh > 0, axis=1)
            max_row_ink = np.max(strip_row_ink) if len(strip_row_ink) > 0 else 0
            rows_with_ink = np.sum(strip_row_ink > 15)

            # A ruling line spans nearly the full width (>60% of page width) but has ink concentrated in <= 10 rows
            is_ruled_line = (max_row_ink > 0.6 * w and rows_with_ink <= 10 and box_h < 70)
            if is_ruled_line and (y1 < 235 or y2 > h - 140):
                continue

            # Header margin or bottom margin ruling check
            if (y1 < 220 and box_h < 65 and ink_density < 0.025) or ((y2 > h - 120) and ink_density < 0.025):
                continue
            if ink_density < 0.008 or strip_ink < 50:
                continue

            # Quality Check 2: Multi-line anomaly sub-segmentation
            # If a bounding box height is exceptionally tall (> 130px), split it internally
            if box_h > 130:
                sub_row_ink = np.sum(strip_thresh > 0, axis=1).astype(np.float32)
                sub_mid = box_h // 2
                # Look for minimum ink in the middle 50% region
                search_start = int(box_h * 0.25)
                search_end = int(box_h * 0.75)
                if search_end > search_start:
                    split_offset = search_start + int(np.argmin(sub_row_ink[search_start:search_end]))
                    split_y = y1 + split_offset
                    # Add first sub-strip
                    strips.append((x1, y1, box_w, split_y - y1))
                    # Add second sub-strip
                    strips.append((x1, split_y, box_w, y2 - split_y))
                    continue

            strips.append((x1, y1, box_w, box_h))

    # 4. Fallback: If projection profile found 0 peaks (irregular or scattered single words)
    if not strips:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, int(w * 0.03)), 3))
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_width = max(25, int(w * 0.03))
        raw_boxes = []
        for c in contours:
            x, y, box_w, box_h = cv2.boundingRect(c)
            if box_h >= min_line_height and box_w >= min_width:
                raw_boxes.append((x, y, box_w, box_h))

        if not raw_boxes:
            x, y, box_w, box_h = cv2.boundingRect(thresh)
            if box_w > 10 and box_h > 10:
                raw_boxes.append((x, y, box_w, box_h))
            else:
                return [], True

        raw_boxes.sort(key=lambda b: b[1])
        strips = raw_boxes

    # 5. Extract LineCrop objects
    line_crops: List[LineCrop] = []
    for idx, (bx, by, bw, bh) in enumerate(strips):
        crop_x1 = max(0, bx)
        crop_y1 = max(0, by)
        crop_x2 = min(w, bx + bw)
        crop_y2 = min(h, by + bh)

        cropped_pil = pil_image_full.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        line_crops.append(LineCrop(
            line_index=idx + 1,
            image=cropped_pil,
            bbox=(int(bx), int(by), int(bw), int(bh))
        ))

    logger.info(f"Segmented page into {len(line_crops)} distinct handwritten lines.")
    return line_crops, False
