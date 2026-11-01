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
