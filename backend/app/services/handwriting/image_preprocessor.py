import logging
import math
import time
from pathlib import Path
from typing import Dict, Any, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def read_image_safe(image_path: Path) -> np.ndarray:
    """
    Safely read an image from disk on Windows supporting UTF-8 paths.
    """
    try:
        data = np.fromfile(str(image_path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not decode image at {image_path}")
        return img
    except Exception as error:
        logger.error(f"Failed to read image '{image_path}': {error}")
        raise


def write_image_safe(image: np.ndarray, output_path: Path) -> None:
    """
    Safely write an image to disk on Windows supporting UTF-8 paths.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower() or ".png"
    success, encoded_img = cv2.imencode(suffix, image)
    if not success:
        raise ValueError(f"Could not encode image for {output_path}")
    encoded_img.tofile(str(output_path))


def calculate_deskew_angle(gray_image: np.ndarray) -> float:
    """
    Calculate skew angle of text lines using Otsu thresholding and minAreaRect.
    Returns angle in degrees (-45 to 45).
    """
    try:
        # Invert binarized image: text is white (255), background is black (0)
        blur = cv2.GaussianBlur(gray_image, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Dilate horizontally to connect words into continuous text line strips
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        angles = []

        h, w = gray_image.shape[:2]
        min_width = w * 0.1  # ignore small noise contours

        for c in contours:
            rect = cv2.minAreaRect(c)
            width = min(rect[1])
            length = max(rect[1])

            if length > min_width and width > 5:
                angle = rect[2]
                # minAreaRect returns angle in [-90, 0)
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle

                if abs(angle) < 45:
                    angles.append(angle)

        if not angles:
            return 0.0

        median_angle = float(np.median(angles))
        return median_angle

    except Exception as error:
        logger.warning(f"Deskew calculation error: {error}. Defaulting to 0.0 deg.")
        return 0.0


def deskew_image(color_image: np.ndarray, angle: float) -> np.ndarray:
    """
    Rotate color image around its center to correct skew.
    """
    if abs(angle) < 0.3:
        return color_image  # negligible skew

    h, w = color_image.shape[:2]
    center = (w // 2, h // 2)

    # Compute rotation matrix with white background padding
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    deskewed = cv2.warpAffine(
        color_image,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )
    return deskewed


def remove_shadows_and_normalize(gray_image: np.ndarray) -> np.ndarray:
    """
    Remove uneven lighting and shadows by morphological background division.
    """
    # Estimate background illumination using large morphological dilation and blur
    dilated = cv2.dilate(gray_image, np.ones((7, 7), np.uint8))
    bg = cv2.medianBlur(dilated, 21)

    # Calculate difference between original and background
    diff = 255 - cv2.absdiff(gray_image, bg)

    # Normalize to full 8-bit dynamic range [0, 255]
    norm = cv2.normalize(
        diff,
        None,
        alpha=0,
        beta=255,
        norm_type=cv2.NORM_MINMAX,
        dtype=cv2.CV_8U
    )
    return norm


def enhance_contrast_clahe(gray_image: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """
    Apply Contrast Limited Adaptive Histogram Equalization (CLAHE) to enhance
    faint pencil and pen strokes without blowing out document backgrounds.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray_image)
    return enhanced


def denoise_image(gray_image: np.ndarray) -> np.ndarray:
    """
    Apply edge-preserving bilateral filter to suppress paper texture and noise
    while preserving sharp character stroke boundaries.
    """
    denoised = cv2.bilateralFilter(gray_image, d=5, sigmaColor=40, sigmaSpace=40)
    return denoised


def preprocess_handwritten_image(
    input_path: Path,
    output_path: Path
) -> Dict[str, Any]:
    """
    Full automated image preprocessing pipeline for handwritten documents.

    Pipeline:
    1. Read original image (safe Windows UTF-8 path handling)
    2. Convert to Grayscale
    3. Detect skew angle and rotate to upright orientation
    4. Remove uneven shadows / phone camera gradients
    5. Enhance faint pencil/pen strokes via CLAHE
    6. Denoise paper artifacts with bilateral filtering
    7. Save clean processed image

    Returns:
        Dict with metrics: resolution, deskew_angle, execution_time_ms.
    """
    start_time = time.time()
    img_bgr = read_image_safe(input_path)
    h, w = img_bgr.shape[:2]

    # Convert to grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 1. Deskew
    angle = calculate_deskew_angle(gray)
    if abs(angle) >= 0.3:
        deskewed_color = deskew_image(img_bgr, angle)
        gray = cv2.cvtColor(deskewed_color, cv2.COLOR_BGR2GRAY)
    else:
        deskewed_color = img_bgr

    # 2. Shadow removal & illumination normalization
    shadow_free = remove_shadows_and_normalize(gray)

    # 3. CLAHE contrast enhancement
    contrast_enhanced = enhance_contrast_clahe(shadow_free, clip_limit=2.0)

    # 4. Bilateral edge-preserving denoising
    clean_gray = denoise_image(contrast_enhanced)

    # Convert back to 3-channel BGR for unified downstream display
    clean_color = cv2.cvtColor(clean_gray, cv2.COLOR_GRAY2BGR)

    write_image_safe(clean_color, output_path)

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    logger.info(
        f"Preprocessed handwritten page {input_path.name} -> {output_path.name} "
        f"({w}x{h}, deskew: {angle:.2f}°, time: {elapsed_ms}ms)"
    )

    return {
        "width": w,
        "height": h,
        "deskew_angle": round(angle, 2),
        "execution_time_ms": elapsed_ms,
        "processed_image_path": str(output_path)
    }

