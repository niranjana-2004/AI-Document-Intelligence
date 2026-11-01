import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image
import cv2

from app.services.handwriting.image_preprocessor import read_image_safe
from app.services.handwriting.line_segmenter import segment_page_into_lines, LineCrop
from app.services.handwriting.ocr_service import recognize_line_image

logger = logging.getLogger(__name__)


def transcribe_page_image(
    image_path: Path,
    original_image_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Execute complete handwriting recognition on a document page image.

    Pipeline:
    1. Read preprocessed image and (if available) original image.
    2. Segment document into individual text lines using horizontal projection analysis.
    3. Crop high-contrast line strips from the preprocessed image.
    4. Run TrOCR beam search inference per line.
    5. Compute per-line and page-level confidence scores.
    6. Reconstruct page transcription preserving reading order and line breaks.

    Returns:
        {
            "full_text": str,
            "confidence_score": float,
            "total_lines": int,
            "is_empty": bool,
            "execution_time_ms": float,
            "lines": [
                {
                    "line_index": int,
                    "text": str,
                    "confidence": float,
                    "bbox": [x, y, w, h],
                    "is_uncertain": bool
                }, ...
            ]
        }
    """
    start_time = time.time()
    proc_img = read_image_safe(image_path)
    h, w = proc_img.shape[:2]

    # Always use the preprocessed, contrast-enhanced image for line segmentation
    # to avoid raw page lighting gradients and ruling line artifacts merging text lines.
    seg_img = proc_img

    # 1. Segment page into text line crops
    line_crops, is_empty = segment_page_into_lines(seg_img)

    if is_empty or not line_crops:
        logger.info(f"Page {image_path.name} is empty or blank; skipping OCR.")
        return {
            "full_text": "",
            "confidence_score": 100.0,
            "total_lines": 0,
            "is_empty": True,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "lines": []
        }

    # 2. Extract line crops from the preprocessed image (high-contrast, shadow-free)
    proc_pil = Image.fromarray(cv2.cvtColor(proc_img, cv2.COLOR_BGR2RGB))
    recognized_lines = []
    text_parts = []
    confidences = []

    for line in line_crops:
        bx, by, bw, bh = line.bbox
        crop_x1 = max(0, bx)
        crop_y1 = max(0, by)
        crop_x2 = min(w, bx + bw)
        crop_y2 = min(h, by + bh)

        line_crop_pil = proc_pil.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        line_result = recognize_line_image(line_crop_pil)
        line_text = line_result.get("text", "").strip()
        line_conf = line_result.get("confidence", 0.0)

        # Filter out empty or rejected hallucination strips
        if line_text:
            text_parts.append(line_text)
            confidences.append(line_conf)
            recognized_lines.append({
                "line_index": len(recognized_lines) + 1,
                "text": line_text,
                "confidence": line_conf,
                "bbox": [int(bx), int(by), int(bw), int(bh)],
                "is_uncertain": line_conf < 60.0
            })

    # 3. Assemble full page text
    full_text = "\n".join(text_parts).strip()
    page_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(
        f"Transcribed {len(recognized_lines)} lines on {image_path.name} in {elapsed_ms}ms "
        f"(confidence: {page_confidence}%)"
    )

    return {
        "full_text": full_text,
        "confidence_score": page_confidence,
        "total_lines": len(recognized_lines),
        "is_empty": False,
        "execution_time_ms": elapsed_ms,
        "lines": recognized_lines
    }
