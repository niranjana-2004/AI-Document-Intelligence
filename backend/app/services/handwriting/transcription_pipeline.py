import logging
import time
from pathlib import Path
from typing import Dict, Any, List
from PIL import Image

from app.services.handwriting.image_preprocessor import read_image_safe
from app.services.handwriting.line_segmenter import segment_page_into_lines
from app.services.handwriting.ocr_service import recognize_line_image

logger = logging.getLogger(__name__)


def transcribe_page_image(image_path: Path) -> Dict[str, Any]:
    """
    Execute complete handwriting recognition on a preprocessed document page image.

    Pipeline:
    1. Read page image
    2. Segment into text line crops in reading order (top-to-bottom)
    3. Run TrOCR small inference per line
    4. Compute per-line and page-level confidence scores
    5. Reconstruct page transcription preserving line breaks

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
                    "bbox": [x, y, w, h]
                }, ...
            ]
        }
    """
    start_time = time.time()
    cv_img = read_image_safe(image_path)

    # 1. Segment page into line crops
    line_crops, is_empty = segment_page_into_lines(cv_img)

    if is_empty:
        logger.info(f"Page {image_path.name} is empty; skipping OCR.")
        return {
            "full_text": "",
            "confidence_score": 100.0,
            "total_lines": 0,
            "is_empty": True,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "lines": []
        }

    recognized_lines = []
    text_parts = []
    confidences = []

    # 2. Recognize text per line
    for line in line_crops:
        line_result = recognize_line_image(line.image)
        line_text = line_result.get("text", "").strip()
        line_conf = line_result.get("confidence", 0.0)

        # Do not discard uncertain text; store it with its confidence flag
        if line_text:
            text_parts.append(line_text)
            confidences.append(line_conf)

        recognized_lines.append({
            "line_index": line.line_index,
            "text": line_text,
            "confidence": line_conf,
            "bbox": list(line.bbox),
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

