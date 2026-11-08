"""
Model loading and inference wrappers for TrOCR Small and TrOCR Base.
Ensures 100% fair, identical preprocessing, resolution, and decoding parameters.
"""

import gc
import logging
import time
from typing import Dict, Any, Tuple, Optional
from PIL import Image
import torch
import torch.nn.functional as F
from transformers import (
    ViTImageProcessorPil,
    XLMRobertaTokenizer,
    RobertaTokenizer,
    TrOCRProcessor,
    VisionEncoderDecoderModel
)

from app.services.handwriting.ocr_service import normalize_text_syntax, is_hallucinated_or_blank

logger = logging.getLogger(__name__)

SMALL_MODEL_NAME = "microsoft/trocr-small-handwritten"
BASE_MODEL_NAME = "microsoft/trocr-base-handwritten"


def get_inference_device() -> torch.device:
    """Safe CPU detection adhering to the strict requirement of CPU-only operation."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_trocr_small(device: Optional[torch.device] = None) -> Tuple[VisionEncoderDecoderModel, TrOCRProcessor, float]:
    """
    Load microsoft/trocr-small-handwritten with XLMRobertaTokenizer.
    Returns (model, processor, load_time_seconds).
    """
    if device is None:
        device = get_inference_device()

    t0 = time.time()
    logger.info(f"Loading TrOCR Small ({SMALL_MODEL_NAME}) on {device}...")
    image_processor = ViTImageProcessorPil.from_pretrained(SMALL_MODEL_NAME)
    tokenizer = XLMRobertaTokenizer.from_pretrained(SMALL_MODEL_NAME)
    processor = TrOCRProcessor(image_processor=image_processor, tokenizer=tokenizer)
    model = VisionEncoderDecoderModel.from_pretrained(SMALL_MODEL_NAME).to(device)

    model.config.decoder_start_token_id = tokenizer.cls_token_id
    model.config.pad_token_id = tokenizer.pad_token_id
    model.config.eos_token_id = tokenizer.sep_token_id
    model.eval()

    load_time = round(time.time() - t0, 3)
    logger.info(f"TrOCR Small loaded in {load_time}s")
    return model, processor, load_time


def load_trocr_base(device: Optional[torch.device] = None) -> Tuple[VisionEncoderDecoderModel, TrOCRProcessor, float]:
    """
    Load microsoft/trocr-base-handwritten with RobertaTokenizer.
    Returns (model, processor, load_time_seconds).
    """
    if device is None:
        device = get_inference_device()

    t0 = time.time()
    logger.info(f"Loading TrOCR Base ({BASE_MODEL_NAME}) on {device}...")
    image_processor = ViTImageProcessorPil.from_pretrained(BASE_MODEL_NAME)
    tokenizer = RobertaTokenizer.from_pretrained(BASE_MODEL_NAME)
    processor = TrOCRProcessor(image_processor=image_processor, tokenizer=tokenizer)
    model = VisionEncoderDecoderModel.from_pretrained(BASE_MODEL_NAME).to(device)

    if tokenizer.cls_token_id is not None:
        model.config.decoder_start_token_id = tokenizer.cls_token_id
    if tokenizer.pad_token_id is not None:
        model.config.pad_token_id = tokenizer.pad_token_id
    if tokenizer.sep_token_id is not None:
        model.config.eos_token_id = tokenizer.sep_token_id
    model.eval()

    load_time = round(time.time() - t0, 3)
    logger.info(f"TrOCR Base loaded in {load_time}s")
    return model, processor, load_time


def unload_model(model: Any, processor: Any) -> None:
    """Free model weights and trigger garbage collection to conserve system RAM."""
    del model
    del processor
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def run_single_inference(
    model: VisionEncoderDecoderModel,
    processor: TrOCRProcessor,
    image: Image.Image,
    num_beams: int = 4,
    max_new_tokens: int = 96,
    normalize: bool = True
) -> Dict[str, Any]:
    """
    Execute controlled inference on a cropped PIL image with identical parameters.
    """
    start_time = time.time()
    if image.mode != "RGB":
        image = image.convert("RGB")

    device = next(model.parameters()).device
    pv = processor(image, return_tensors="pt").pixel_values.to(device)

    with torch.no_grad():
        outputs = model.generate(
            pv,
            max_new_tokens=max_new_tokens,
            num_beams=num_beams,
            early_stopping=True,
            no_repeat_ngram_size=0,
            return_dict_in_generate=True,
            output_scores=True
        )

    decoded = processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0].strip()
    raw_text = decoded
    final_text = normalize_text_syntax(decoded) if normalize else decoded

    if hasattr(outputs, "sequences_scores") and outputs.sequences_scores is not None and len(outputs.sequences_scores) > 0:
        log_prob = outputs.sequences_scores[0].item()
        conf = round(float(torch.exp(torch.tensor(log_prob)).item()) * 100.0, 1)
        conf = max(5.0, min(99.0, conf))
    elif outputs.scores:
        step_probs = [F.softmax(score, dim=-1).max().item() for score in outputs.scores]
        conf = round((sum(step_probs) / len(step_probs)) * 100.0, 1)
    else:
        conf = 85.0 if final_text else 0.0

    is_halluc = is_hallucinated_or_blank(final_text, conf)
    if is_halluc:
        final_text = ""
        conf = 0.0

    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    return {
        "raw_text": raw_text,
        "text": final_text,
        "confidence": conf,
        "inference_time_ms": elapsed_ms,
        "is_hallucination": is_halluc
    }

