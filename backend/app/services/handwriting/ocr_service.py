import logging
import re
import threading
import time
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageEnhance
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)

MODEL_NAME = "microsoft/trocr-small-handwritten"

# Known vision-model hallucination patterns (Wikipedia metadata / repetitive token degeneration)
HALLUCINATIONS = [
    "this article does not cite",
    "helplearn to edit",
    "community portal",
    "what links hererelated",
    "what links here",
    "special pagespermanent",
    "special pages",
    "unsourced statements",
    "vtemunicipalities",
    "increvementary safety",
    "archaeolog",
    "a b c d e",
    "0 0 0 0",
    "000 000 000",
    "mmenwomen",
    "jump to navigation",
    "jump to search",
    "from wikipedia",
    "navigation search",
    "recent changes",
    "upload file",
    "permanent link",
    "page information",
    "cite this page",
    "wikimedia commons",
    "hidden categories",
]


def normalize_text_syntax(text: str) -> str:
    """
    Standardize typography, punctuation spacing, bracket alignment, and hyphens
    without fragile hardcoded domain word replacements that corrupt unrelated academic disciplines.
    """
    if not text:
        return ""
    # Remove space before standard punctuation marks
    cleaned = re.sub(r'\s+([.,;:!?])', r'\1', text)
    # Clean opening and closing brackets
    cleaned = re.sub(r'([(\[{])\s+', r'\1', cleaned)
    cleaned = re.sub(r'\s+([)\]}])', r'\1', cleaned)
    # Fix detached hyphenations (e.g. 'three - way' -> 'three-way', 'per - packet' -> 'per-packet')
    cleaned = re.sub(r'(\b[A-Za-z0-9]+)\s*-\s*([A-Za-z0-9]+\b)', r'\1-\2', cleaned)
    # Standardize bullet markers at line start
    cleaned = re.sub(r'^[•*]\s*', '- ', cleaned)
    # Collapse multiple whitespaces
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip(' "\'')
    return cleaned


def is_hallucinated_or_blank(text: str, conf: float) -> bool:
    """Check if decoded output is a degenerated model hallucination or pure whitespace."""
    t_low = text.lower()
    for h in HALLUCINATIONS:
        if h in t_low:
            return True
    if len(re.sub(r'[\W\d_]+', '', text)) < 2:
        return True
    return False


_ocr_model: Optional[Any] = None
_ocr_processor: Optional[Any] = None
_ocr_lock = threading.Lock()


def get_ocr_engine() -> Tuple[Any, Any]:
    """
    Lazily initialize and cache the TrOCR small handwritten model and processor
    as a thread-safe singleton.
    """
    global _ocr_model, _ocr_processor
    if _ocr_model is None or _ocr_processor is None:
        with _ocr_lock:
            if _ocr_model is None or _ocr_processor is None:
                from transformers import (
                    ViTImageProcessorPil,
                    XLMRobertaTokenizer,
                    TrOCRProcessor,
                    VisionEncoderDecoderModel
                )

                logger.info(f"Loading handwriting OCR model: {MODEL_NAME}...")
                start_time = time.time()

                try:
                    image_processor = ViTImageProcessorPil.from_pretrained(MODEL_NAME)
                    tokenizer = XLMRobertaTokenizer.from_pretrained(MODEL_NAME)
                    processor = TrOCRProcessor(
                        image_processor=image_processor,
                        tokenizer=tokenizer
                    )

                    model = VisionEncoderDecoderModel.from_pretrained(MODEL_NAME)
                    # Configure decoder start, pad, and eos tokens
                    model.config.decoder_start_token_id = tokenizer.cls_token_id
                    model.config.pad_token_id = tokenizer.pad_token_id
                    model.config.eos_token_id = tokenizer.sep_token_id
                    model.eval()

                    _ocr_processor = processor
                    _ocr_model = model

                    elapsed = round(time.time() - start_time, 2)
                    logger.info(f"Successfully loaded and cached {MODEL_NAME} in {elapsed}s")

                except Exception as error:
                    logger.error(f"Failed to load OCR model '{MODEL_NAME}': {error}")
                    raise RuntimeError(
                        f"Handwriting OCR engine initialization failed: {error}"
                    ) from error

    return _ocr_model, _ocr_processor


def recognize_line_image(line_image: Image.Image) -> Dict[str, Any]:
    """
    Perform multi-pass handwriting recognition on an individual cropped text line image
    using beam search decoding with resolution-aware enhancement and uncertainty scoring.

    Controlled Multi-Pass:
    - Pass 1: Standard contrast crop.
    - Pass 2: If Pass 1 confidence < 70% or crop is small/faint, re-evaluate with
      adaptive sharpness boost and contrast enhancement. Chooses the candidate with
      higher confidence.

    Returns:
        {
            "text": str,
            "confidence": float,
            "is_uncertain": bool,
            "is_hallucination": bool,
            "inference_time_ms": float
        }
    """
    model, processor = get_ocr_engine()
    start_time = time.time()

    # Ensure RGB mode
    if line_image.mode != "RGB":
        line_image = line_image.convert("RGB")

    def _infer(img: Image.Image) -> Tuple[str, float]:
        pv = processor(img, return_tensors="pt").pixel_values
        with torch.no_grad():
            outputs = model.generate(
                pv,
                max_new_tokens=96,
                num_beams=4,
                early_stopping=True,
                no_repeat_ngram_size=0,
                return_dict_in_generate=True,
                output_scores=True
            )
        decoded = processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0].strip()
        cleaned = normalize_text_syntax(decoded)
        if hasattr(outputs, "sequences_scores") and outputs.sequences_scores is not None:
            log_prob = outputs.sequences_scores[0].item()
            conf = round(float(torch.exp(torch.tensor(log_prob)).item()) * 100.0, 1)
            conf = max(5.0, min(99.0, conf))
        elif outputs.scores:
            step_probs = [F.softmax(score, dim=-1).max().item() for score in outputs.scores]
            conf = round((sum(step_probs) / len(step_probs)) * 100.0, 1)
        else:
            conf = 85.0 if cleaned else 0.0
        return cleaned, conf

    try:
        # Pass 1: Standard crop
        t1, c1 = _infer(line_image)

        # Pass 2: Enhanced sharpness & contrast for low-confidence strips
        if c1 < 70.0 and line_image.width > 20 and line_image.height > 10:
            enh = ImageEnhance.Sharpness(line_image).enhance(1.6)
            enh = ImageEnhance.Contrast(enh).enhance(1.25)
            t2, c2 = _infer(enh)
            if c2 > c1 + 3.0:
                selected_text = t2
                selected_conf = c2
            else:
                selected_text = t1
                selected_conf = c1
        else:
            selected_text = t1
            selected_conf = c1

        # Check for model degeneration / web hallucinations
        if is_hallucinated_or_blank(selected_text, selected_conf):
            return {
                "text": "",
                "confidence": 0.0,
                "is_uncertain": True,
                "inference_time_ms": round((time.time() - start_time) * 1000, 2),
                "is_hallucination": True
            }

        final_text = normalize_text_syntax(selected_text)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "text": final_text,
            "confidence": selected_conf,
            "is_uncertain": selected_conf < 65.0,
            "is_hallucination": False,
            "inference_time_ms": elapsed_ms
        }

    except Exception as error:
        logger.error(f"Error during line OCR recognition: {error}")
        return {
            "text": "",
            "confidence": 0.0,
            "is_uncertain": True,
            "inference_time_ms": round((time.time() - start_time) * 1000, 2),
            "error": str(error)
        }
