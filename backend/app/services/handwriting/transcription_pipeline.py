import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image
import cv2

from app.core.config import settings
from app.services.handwriting.image_preprocessor import read_image_safe
from app.services.handwriting.line_segmenter import segment_page_into_lines, LineCrop
from app.services.handwriting.ocr_service import recognize_line_image
from app.services.handwriting.document_structure_service import (
    analyze_document_structure,
    reconstruct_structured_markdown
)
from app.services.handwriting.terminology_service import extract_document_terminology
from app.services.handwriting.technical_recovery_service import recover_technical_line
from app.services.handwriting.word_context_recovery_service import DocumentConsistencyIndex

logger = logging.getLogger(__name__)


def transcribe_page_image(
    image_path: Path,
    original_image_path: Optional[Path] = None,
    subject: Optional[str] = None,
    page_num: int = 1,
    doc_index: Optional[Any] = None,
    force_layout_guided: bool = False
) -> Dict[str, Any]:
    """
    Execute complete handwriting recognition on a document page image.

    If LAYOUT_GUIDED_OCR_ENABLED is enabled (or force_layout_guided=True),
    delegates to Layout Intelligence 4.0 region-aware OCR with safety fallback.
    Otherwise runs frozen production OCR 3.5 pipeline directly.
    """
    layout_fallback_triggered = False
    layout_fallback_reason = None
    if force_layout_guided or getattr(settings, "LAYOUT_GUIDED_OCR_ENABLED", False):
        try:
            from app.services.handwriting.layout_guided_ocr_service import transcribe_page_image_layout_guided
            return transcribe_page_image_layout_guided(
                image_path=image_path,
                original_image_path=original_image_path,
                subject=subject,
                page_num=page_num,
                doc_index=doc_index
            )
        except Exception as layout_err:
            logger.warning(
                f"Layout-guided OCR encountered unhandled exception on {image_path.name}: {layout_err}. "
                "Executing immediate safe fallback to baseline OCR 3.5."
            )
            layout_fallback_triggered = True
            layout_fallback_reason = f"transcription_pipeline_exception: {str(layout_err)}"
    """
    Execute complete handwriting recognition on a document page image.

    Pipeline:
    1. Read preprocessed image and (if available) original image.
    2. Segment document into individual text lines using ruling-line suppressed projection analysis.
    3. Crop high-contrast line strips from the preprocessed image with adaptive margin padding.
    4. Run controlled multi-pass TrOCR inference per line.
    5. Compute per-line and page-level confidence scores with uncertainty indicators.
    6. Analyze document layout hierarchy (titles, headings, paragraphs, lists, math).
    7. Synthesize structured layout and semantic markdown preserving paragraph flow.

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
            ],
            "structured_layout": {
                "blocks": [...],
                "total_blocks": int,
                "has_headings": bool,
                "has_lists": bool,
                "has_math": bool
            }
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
            "lines": [],
            "structured_layout": {
                "blocks": [],
                "total_blocks": 0,
                "has_headings": False,
                "has_lists": False,
                "has_math": False
            },
            "technical_corrections": [],
            "tokens": [],
            "raw_text": "",
            "recovered_text": "",
            "ocr_mode": "ocr35_baseline",
            "layout_enabled": False,
            "fallback_used": False,
            "fallback_reason": None
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
                "is_uncertain": line_conf < 65.0
            })

    # 3. Technical OCR Recovery Layer
    vocab_index = extract_document_terminology(text_parts, subject=subject)
    if doc_index is None:
        raw_lines_by_page = {page_num: text_parts}
        doc_index = DocumentConsistencyIndex(raw_lines_by_page)
    recovered_lines_data = []
    technical_corrections = []
    page_tokens = []

    for l_item in recognized_lines:
        l_idx = l_item["line_index"]
        l_text = l_item["text"]
        l_conf = l_item["confidence"]
        bx, by, bw, bh = l_item["bbox"]
        crop_bgr = proc_img[max(0, by):min(h, by+bh), max(0, bx):min(w, bx+bw)] if (bh > 0 and bw > 0) else None

        rec_text, corrs, l_tokens = recover_technical_line(
            raw_line_text=l_text,
            line_idx=l_idx,
            page_num=page_num,
            vocab_index=vocab_index,
            line_crop_bgr=crop_bgr,
            line_conf=l_conf,
            line_bbox=[int(bx), int(by), int(bw), int(bh)],
            return_tokens=True,
            doc_index=doc_index
        )
        l_item["recovered_text"] = rec_text
        l_item["tokens"] = l_tokens
        page_tokens.extend(l_tokens)
        technical_corrections.extend(corrs)
        recovered_lines_data.append({
            "line_index": l_idx,
            "text": rec_text,
            "confidence": l_conf,
            "bbox": l_item["bbox"],
            "is_uncertain": l_item["is_uncertain"]
        })

    # 4. Analyze document structure (using recovered technical text for clean semantic hierarchy)
    structure = analyze_document_structure(recovered_lines_data, page_width=w, page_height=h)
    structured_markdown = reconstruct_structured_markdown(structure["blocks"])

    raw_text = "\n".join(text_parts).strip()
    recovered_text = "\n".join(l["text"] for l in recovered_lines_data).strip()
    full_text = structured_markdown if structured_markdown else recovered_text
    page_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(
        f"Transcribed {len(recognized_lines)} lines on {image_path.name} in {elapsed_ms}ms "
        f"(confidence: {page_confidence}%, blocks: {structure['total_blocks']}, corrections: {len(technical_corrections)})"
    )

    return {
        "raw_text": raw_text,
        "recovered_text": recovered_text,
        "full_text": full_text,
        "confidence_score": page_confidence,
        "total_lines": len(recognized_lines),
        "is_empty": False,
        "execution_time_ms": elapsed_ms,
        "lines": recognized_lines,
        "structured_layout": structure,
        "technical_corrections": technical_corrections,
        "tokens": page_tokens,
        "ocr_mode": "ocr35_baseline_fallback" if layout_fallback_triggered else "ocr35_baseline",
        "layout_enabled": True if layout_fallback_triggered else False,
        "fallback_used": layout_fallback_triggered,
        "fallback_reason": layout_fallback_reason
    }
