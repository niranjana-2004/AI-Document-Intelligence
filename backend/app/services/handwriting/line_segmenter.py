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
    scale-invariant horizontal projection profile analysis with notebook ruling-line
    suppression, adaptive peak-valley detection, and natural reading order.

    Scale-Invariant Features:
    - Relative thresholds derived from image dimensions (H, W).
    - Horizontal morphological opening to identify and subtract printed notebook ruling lines
      prior to profile computation (prevents false margin cuts and ascender/descender slicing).
    - Adaptive Gaussian profile smoothing based on page height.
    - Anomaly detection based on median line height rather than fixed pixel limits.
    - Adaptive bounding box horizontal and vertical padding.

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

    # 3. Detect and suppress horizontal printed notebook ruling lines for profiling
    # Ruling lines span > 15% of width with 1-2 pixel vertical thickness.
    line_len = max(30, int(w * 0.15))
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1))
    ruling_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h)
    
    # Text-only ink mask prevents horizontal ruling lines from forming fake peaks or skewing valleys
    text_thresh = cv2.subtract(thresh, ruling_lines)

    # 4. Horizontal Projection Profile & Peak Detection
    row_ink = np.sum(text_thresh > 0, axis=1).astype(np.float32)
    # Adaptive Gaussian smoothing parameter based on page height
    sigma = max(6.0, min(16.0, h / 140.0))
    smoothed = gaussian_filter1d(row_ink, sigma=sigma)

    # Minimum line distance (~1.8% of page height)
    min_dist = max(20, int(h * 0.018))
    # Adaptive prominence based on active ink rows
    active_ink = smoothed[smoothed > 0]
    prominence = max(18.0, float(np.percentile(active_ink, 20)) * 0.4) if len(active_ink) > 0 else 20.0
    peaks, _ = find_peaks(smoothed, distance=min_dist, prominence=prominence)

    # Filter out residual noise peaks (below 1.5% of page width ink)
    min_peak_ink = max(30.0, 0.015 * w)
    valid_peaks = [p for p in peaks if smoothed[p] >= min_peak_ink]

    pil_image_full = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    strips = []

    if len(valid_peaks) >= 1:
        # Determine top boundary using first ink in text_thresh near the first peak
        search_top = max(0, int(valid_peaks[0] - (min_dist * 1.5)))
        first_ink = np.where(row_ink[search_top:valid_peaks[0]] > max(8, 0.004 * w))[0]
        if len(first_ink) > 0:
            top_y = max(0, search_top + first_ink[0] - padding)
        else:
            top_y = max(0, int(valid_peaks[0] - (min_dist * 0.8)))

        valleys = [top_y]
        for i in range(len(valid_peaks) - 1):
            p1 = valid_peaks[i]
            p2 = valid_peaks[i + 1]
            # Valley is the local minimum ink row between two consecutive text line peaks
            valley_offset = int(np.argmin(smoothed[p1:p2]))
            valley_y = p1 + valley_offset
            valleys.append(valley_y)

        # Determine bottom boundary using last ink in text_thresh near the last peak
        search_bottom = min(h, int(valid_peaks[-1] + (min_dist * 1.5)))
        last_ink = np.where(row_ink[valid_peaks[-1]:search_bottom] > max(8, 0.004 * w))[0]
        if len(last_ink) > 0:
            bottom_y = min(h, valid_peaks[-1] + last_ink[-1] + padding)
        else:
            bottom_y = min(h, int(valid_peaks[-1] + (min_dist * 0.8)))
        valleys.append(bottom_y)

        # Calculate preliminary line heights for scale-invariant anomaly detection
        prelim_heights = [valleys[i+1] - valleys[i] for i in range(len(valleys)-1) if valleys[i+1] - valleys[i] > 10]
        median_line_h = float(np.median(prelim_heights)) if prelim_heights else (h * 0.035)

        for i in range(len(valleys) - 1):
            y1 = max(0, valleys[i])
            y2 = min(h, valleys[i + 1])
            box_h = y2 - y1
            if box_h < min_line_height:
                continue

            # Detect horizontal word bounds in this strip using Otsu threshold
            strip_thresh = thresh[y1:y2, :]
            col_sums = np.sum(strip_thresh > 0, axis=0)
            cols = np.where(col_sums > 2)[0]
            if len(cols) > 0:
                pad_x = max(8, int(w * 0.008))
                x1 = max(0, int(cols[0]) - pad_x)
                x2 = min(w, int(cols[-1]) + pad_x)
            else:
                x1, x2 = 0, w

            box_w = max(10, x2 - x1)

            # Quality Check 1: Reject empty notebook ruling lines or blank margins
            strip_ink = np.sum(strip_thresh > 0)
            strip_area = box_w * box_h
            ink_density = (strip_ink / strip_area) if strip_area > 0 else 0.0

            # Ruling line check: spans nearly full page width with very thin vertical ink
            strip_row_ink = np.sum(strip_thresh > 0, axis=1)
            max_row_ink = np.max(strip_row_ink) if len(strip_row_ink) > 0 else 0
            rows_with_ink = np.sum(strip_row_ink > 15)

            is_pure_ruling_line = (max_row_ink > 0.65 * w and rows_with_ink <= 8 and box_h < median_line_h * 0.6)
            if is_pure_ruling_line and (y1 < h * 0.12 or y2 > h * 0.88):
                continue

            if ink_density < 0.005 or strip_ink < 35:
                continue

            # Quality Check 2: Scale-invariant multi-line anomaly sub-segmentation
            # Split internally ONLY if box is significantly taller than median line height (> 2.3x)
            if box_h > median_line_h * 2.3:
                sub_row_ink = np.sum(strip_thresh > 0, axis=1).astype(np.float32)
                search_start = int(box_h * 0.28)
                search_end = int(box_h * 0.72)
                if search_end > search_start:
                    split_offset = search_start + int(np.argmin(sub_row_ink[search_start:search_end]))
                    split_y = y1 + split_offset
                    # Add first sub-strip
                    strips.append((x1, y1, box_w, split_y - y1))
                    # Add second sub-strip
                    strips.append((x1, split_y, box_w, y2 - split_y))
                    continue

            strips.append((x1, y1, box_w, box_h))

    # 5. Fallback: If projection profile found 0 peaks (irregular or scattered single words)
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

    # Sort strips by natural reading order (primarily vertical, then horizontal)
    strips.sort(key=lambda b: (b[1], b[0]))

    # 6. Extract LineCrop objects with safe padding
    line_crops: List[LineCrop] = []
    pad_y = max(4, int(padding * 0.7))
    for idx, (bx, by, bw, bh) in enumerate(strips):
        crop_x1 = max(0, bx)
        crop_y1 = max(0, by - pad_y)
        crop_x2 = min(w, bx + bw)
        crop_y2 = min(h, by + bh + pad_y)

        cropped_pil = pil_image_full.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        line_crops.append(LineCrop(
            line_index=idx + 1,
            image=cropped_pil,
            bbox=(int(bx), int(by), int(bw), int(bh))
        ))

    logger.info(f"Segmented page into {len(line_crops)} distinct handwritten lines.")
    return line_crops, False
