import logging
import threading
import time
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)

MODEL_NAME = "microsoft/trocr-small-handwritten"

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
                    # Configure decoder start and pad tokens
                    model.config.decoder_start_token_id = tokenizer.cls_token_id
                    model.config.pad_token_id = tokenizer.pad_token_id
                    model.config.eos_token_id = tokenizer.eos_token_id
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
    Perform handwriting recognition on an individual cropped text line image.

    Returns:
        {
            "text": str,
            "confidence": float (0.0 to 100.0),
            "inference_time_ms": float
        }
    """
    model, processor = get_ocr_engine()
    start_time = time.time()

    # Ensure RGB
    if line_image.mode != "RGB":
        line_image = line_image.convert("RGB")

    try:
        pixel_values = processor(line_image, return_tensors="pt").pixel_values

        with torch.no_grad():
            outputs = model.generate(
                pixel_values,
                max_new_tokens=45,
                return_dict_in_generate=True,
                output_scores=True
            )

        text = processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0].strip()

        # Calculate actual confidence score from token probability distribution
        if outputs.scores:
            step_probs = [
                F.softmax(score, dim=-1).max().item()
                for score in outputs.scores
            ]
            confidence = round((sum(step_probs) / len(step_probs)) * 100.0, 1)
        else:
            confidence = 80.0 if text else 0.0

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "text": text,
            "confidence": confidence,
            "inference_time_ms": elapsed_ms
        }

    except Exception as error:
        logger.error(f"Error during line OCR inference: {error}")
        return {
            "text": "",
            "confidence": 0.0,
            "inference_time_ms": round((time.time() - start_time) * 1000, 2),
            "error": str(error)
        }

