import logging
import math
import time
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
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
    # Guard against completely uniform / blank pages
    if float(np.std(gray_image)) < 3.0:
        return gray_image

    # Estimate background illumination using large morphological dilation and blur
    dilated = cv2.dilate(gray_image, np.ones((7, 7), np.uint8))
    bg = cv2.medianBlur(dilated, 21)

    # Calculate difference between original and background
    diff = 255 - cv2.absdiff(gray_image, bg)

    min_val, max_val, _, _ = cv2.minMaxLoc(diff)
    if max_val - min_val < 5:
        return gray_image

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


def generate_page_stages(
    original_path: Path,
    stages_dir: Path,
    force: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate and persist intermediate OpenCV preprocessing stage images and thumbnails,
    returning detailed genuine metadata for each stage.
    Caches stages and metadata on disk for instantaneous subsequent loads.
    """
    import json
    stages_dir.mkdir(parents=True, exist_ok=True)
    metadata_file = stages_dir / "stages_metadata.json"

    # Fast path: Return cached stages if already generated
    if not force and metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if len(cached) == 6:
                    return cached
        except Exception as read_err:
            logger.warning(f"Failed to read cached stages metadata: {read_err}; regenerating.")

    img_bgr = read_image_safe(original_path)
    h, w = img_bgr.shape[:2]

    def save_stage_image_and_thumb(img_arr: np.ndarray, base_name: str):
        full_path = stages_dir / f"{base_name}.png"
        thumb_path = stages_dir / f"{base_name}_thumb.png"
        write_image_safe(img_arr, full_path)

        thumb_scale = min(280.0 / w, 280.0 / h)
        tw, th = max(10, int(w * thumb_scale)), max(10, int(h * thumb_scale))
        thumb_img = cv2.resize(img_arr, (tw, th), interpolation=cv2.INTER_AREA)
        write_image_safe(thumb_img, thumb_path)
        return full_path, thumb_path

    stages = []

    # Stage 1: Original
    t0 = time.time()
    save_stage_image_and_thumb(img_bgr, "stage_1_original")
    t1_ms = round((time.time() - t0) * 1000, 1)
    stages.append({
        "stage_id": "original",
        "stage_number": 1,
        "title": "Original Capture",
        "subtitle": "Raw input photograph/scan",
        "description": "The untouched handwritten document image exactly as uploaded, showing natural paper color, lighting variations, and physical imperfections.",
        "technical_detail": "Direct decoding of input image stream with color profile preservation.",
        "metrics": {
            "width": w,
            "height": h,
            "execution_time_ms": t1_ms,
            "mean_brightness": round(float(np.mean(img_bgr)), 1),
            "contrast_std": round(float(np.std(img_bgr)), 1)
        }
    })

    # Stage 2: Deskewed
    t0 = time.time()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    angle = calculate_deskew_angle(gray)
    is_applied = abs(angle) >= 0.3
    deskewed_color = deskew_image(img_bgr, angle) if is_applied else img_bgr.copy()
    save_stage_image_and_thumb(deskewed_color, "stage_2_deskewed")
    t2_ms = round((time.time() - t0) * 1000, 1)
    stages.append({
        "stage_id": "deskewed",
        "stage_number": 2,
        "title": "Automated Deskewing",
        "subtitle": "Orientation & angle correction",
        "description": "Calculates the median tilt of text line bounding boxes using Otsu binarization and minAreaRect contours, then applies affine rotation to straighten text baselines.",
        "technical_detail": f"cv2.minAreaRect() angle detection followed by cv2.warpAffine() (detected: {angle:.2f}°).",
        "metrics": {
            "width": w,
            "height": h,
            "detected_angle": round(angle, 2),
            "applied_correction": round(-angle, 2) if is_applied else 0.0,
            "is_applied": is_applied,
            "execution_time_ms": t2_ms,
            "mean_brightness": round(float(np.mean(deskewed_color)), 1),
            "contrast_std": round(float(np.std(deskewed_color)), 1)
        }
    })

    # Stage 3: Normalized
    t0 = time.time()
    dgray = cv2.cvtColor(deskewed_color, cv2.COLOR_BGR2GRAY)
    shadow_free = remove_shadows_and_normalize(dgray)
    save_stage_image_and_thumb(shadow_free, "stage_3_normalized")
    t3_ms = round((time.time() - t0) * 1000, 1)
    stages.append({
        "stage_id": "normalized",
        "stage_number": 3,
        "title": "Illumination Normalization",
        "subtitle": "Shadow removal & background leveling",
        "description": "Estimates uneven background lighting using morphological dilation and large median filtering, then subtracts the illumination field to produce an even, clean background.",
        "technical_detail": "cv2.dilate(7x7) + cv2.medianBlur(21) background estimation followed by difference normalization.",
        "metrics": {
            "width": w,
            "height": h,
            "execution_time_ms": t3_ms,
            "mean_brightness": round(float(np.mean(shadow_free)), 1),
            "contrast_std": round(float(np.std(shadow_free)), 1)
        }
    })

    # Stage 4: CLAHE
    t0 = time.time()
    contrast_enhanced = enhance_contrast_clahe(shadow_free, clip_limit=2.0)
    save_stage_image_and_thumb(contrast_enhanced, "stage_4_clahe")
    t4_ms = round((time.time() - t0) * 1000, 1)
    stages.append({
        "stage_id": "clahe",
        "stage_number": 4,
        "title": "CLAHE Contrast Enhancement",
        "subtitle": "Stroke contrast amplification",
        "description": "Applies Contrast Limited Adaptive Histogram Equalization in 8x8 localized tiles to bring out faint pencil and light pen strokes without blowing out document highlights.",
        "technical_detail": "cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).",
        "metrics": {
            "width": w,
            "height": h,
            "clip_limit": 2.0,
            "tile_grid": "8x8",
            "execution_time_ms": t4_ms,
            "mean_brightness": round(float(np.mean(contrast_enhanced)), 1),
            "contrast_std": round(float(np.std(contrast_enhanced)), 1)
        }
    })

    # Stage 5: Denoised
    t0 = time.time()
    clean_gray = denoise_image(contrast_enhanced)
    save_stage_image_and_thumb(clean_gray, "stage_5_denoised")
    t5_ms = round((time.time() - t0) * 1000, 1)
    stages.append({
        "stage_id": "denoised",
        "stage_number": 5,
        "title": "Bilateral Denoising",
        "subtitle": "Edge-preserving paper smoothing",
        "description": "Filters out paper texture grain, scanner artifacts, and sensor noise while strictly preserving sharp high-frequency edges of handwriting ink strokes.",
        "technical_detail": "cv2.bilateralFilter(d=5, sigmaColor=40, sigmaSpace=40).",
        "metrics": {
            "width": w,
            "height": h,
            "diameter": 5,
            "sigma_color": 40,
            "execution_time_ms": t5_ms,
            "mean_brightness": round(float(np.mean(clean_gray)), 1),
            "contrast_std": round(float(np.std(clean_gray)), 1)
        }
    })

    # Stage 6: Final
    t0 = time.time()
    clean_color = cv2.cvtColor(clean_gray, cv2.COLOR_GRAY2BGR)
    save_stage_image_and_thumb(clean_color, "stage_6_final")
    t6_ms = round((time.time() - t0) * 1000, 1)
    stages.append({
        "stage_id": "final",
        "stage_number": 6,
        "title": "Final Enhanced Output",
        "subtitle": "OCR-ready pipeline image",
        "description": "The finalized clean, deskewed, high-contrast handwritten page prepared for horizontal projection profile line segmentation and TrOCR recognition.",
        "technical_detail": "Consolidated 3-channel BGR output matching the exact input supplied to the TrOCR neural pipeline.",
        "metrics": {
            "width": w,
            "height": h,
            "channels": 3,
            "execution_time_ms": t6_ms,
            "mean_brightness": round(float(np.mean(clean_color)), 1),
            "contrast_std": round(float(np.std(clean_color)), 1)
        }
    })

    # Write metadata file for subsequent fast loads
    try:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(stages, f, indent=2)
    except Exception as w_err:
        logger.warning(f"Could not persist stages metadata JSON: {w_err}")

    return stages

