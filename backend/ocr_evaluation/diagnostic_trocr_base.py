"""
Diagnostic script for investigating TrOCR Base artifacts (leading #, quote characters, trailing ..., etc.)
Strictly isolated in backend/ocr_evaluation/ without modifying production code.
"""

import os
import sys
import time
sys.stdout.reconfigure(line_buffering=True)
import json
import logging
from PIL import Image
import torch
import torch.nn.functional as F
from transformers import (
    ViTImageProcessorPil,
    RobertaTokenizer,
    XLMRobertaTokenizer,
    TrOCRProcessor,
    VisionEncoderDecoderModel
)

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.core.database import SessionLocal
from app.models.handwritten_page import HandwrittenPage
from app.services.handwriting.ocr_service import normalize_text_syntax
from ocr_evaluation.metrics import calculate_cer, calculate_wer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SMALL_MODEL_NAME = "microsoft/trocr-small-handwritten"
BASE_MODEL_NAME = "microsoft/trocr-base-handwritten"


def get_diagnostic_line_crops():
    """Load 4 key diagnostic lines from Document #12 Page 1."""
    db = SessionLocal()
    try:
        page = db.query(HandwrittenPage).filter(
            HandwrittenPage.document_id == 12,
            HandwrittenPage.page_number == 1
        ).first()
        if not page or not page.ocr_metadata:
            raise RuntimeError("Page 1 of Document #12 not found in DB.")

        processed_img_path = page.processed_image_path
        if not os.path.isabs(processed_img_path):
            processed_img_path = os.path.join(backend_dir, processed_img_path)

        full_img = Image.open(processed_img_path).convert("RGB")
        lines_data = page.ocr_metadata.get("lines", [])

        # Selected diagnostic lines:
        # Line 0: Header with student name Niranjana -> Base produced '# Niranjana A!...'
        # Line 1: Title TCP SYN Flood -> Base produced '# TCP " Attacks 1. TCP SYN Hood...'
        # Line 3: TV three-way vs TCP three-way... -> Base produced '...TCP three-way... # handshake...'
        # Line 7: Handshakes / homelessness / peers -> Base produced 'homelessness and never finishing them... genuine peers'
        target_indices = [0, 1, 3, 7]
        samples = []

        ground_truths = {
            0: "Niranjana A S 21BIT042 Notes on TCP Attacks",
            1: "1. TCP SYN Flood",
            3: "exploits the TCP three-way handshake (SYN, SYN-ACK, ACK). TCP is",
            7: "many handshakes and never finishing them, until the server has no room left for genuine users. It is"
        }

        for idx in target_indices:
            if idx < len(lines_data):
                ld = lines_data[idx]
                bbox = ld.get("bbox", [])
                x, y, w, h = bbox
                # Crop with identical logic to production line_segmenter
                crop = full_img.crop((x, y, x + w, y + h))
                samples.append({
                    "line_idx": idx,
                    "bbox": bbox,
                    "crop": crop,
                    "gt": ground_truths.get(idx, ld.get("text", ""))
                })
        return samples
    finally:
        db.close()


def run_diagnostics():
    device = torch.device("cpu")
    torch.set_num_threads(12)

    logger.info("--- Step 1: Inspecting Base Tokenizer and Vocab ---")
    base_tok = RobertaTokenizer.from_pretrained(BASE_MODEL_NAME)
    small_tok = XLMRobertaTokenizer.from_pretrained(SMALL_MODEL_NAME)

    logger.info(f"Base cls_token_id: {base_tok.cls_token_id} ({base_tok.cls_token})")
    logger.info(f"Base sep_token_id: {base_tok.sep_token_id} ({base_tok.sep_token})")
    logger.info(f"Base pad_token_id: {base_tok.pad_token_id} ({base_tok.pad_token})")
    logger.info(f"Base bos_token_id: {base_tok.bos_token_id} ({base_tok.bos_token})")
    logger.info(f"Base eos_token_id: {base_tok.eos_token_id} ({base_tok.eos_token})")

    logger.info(f"Base token for '#': {base_tok.encode('#', add_special_tokens=False)} | '{base_tok.tokenize('#')}'")
    logger.info(f"Base token for ' #': {base_tok.encode(' #', add_special_tokens=False)} | '{base_tok.tokenize(' #')}'")
    logger.info(f"Base token for '...': {base_tok.encode('...', add_special_tokens=False)} | '{base_tok.tokenize('...')}'")
    logger.info(f"Base token for 'homelessness': {base_tok.encode('homelessness', add_special_tokens=False)}")
    logger.info(f"Base token for 'handshakes': {base_tok.encode('handshakes', add_special_tokens=False)}")

    logger.info("\n--- Step 2: Loading TrOCR Base Model ---")
    img_processor = ViTImageProcessorPil.from_pretrained(BASE_MODEL_NAME)
    processor = TrOCRProcessor(image_processor=img_processor, tokenizer=base_tok)
    model = VisionEncoderDecoderModel.from_pretrained(BASE_MODEL_NAME).to(device)
    model.eval()

    logger.info(f"Native model.generation_config.decoder_start_token_id: {getattr(model.generation_config, 'decoder_start_token_id', None)}")
    logger.info(f"Native model.generation_config.eos_token_id: {getattr(model.generation_config, 'eos_token_id', None)}")
    logger.info(f"Native model.generation_config.bos_token_id: {getattr(model.generation_config, 'bos_token_id', None)}")

    samples = get_diagnostic_line_crops()
    logger.info(f"Loaded {len(samples)} diagnostic line crops.")

    # Configurations to test:
    # Config A: OCR 3.4 Evaluation default (decoder_start_token_id = cls_token_id = 0, num_beams=4)
    # Config B: Native generation_config (decoder_start_token_id = 2, num_beams=4)
    # Config C: Native generation_config with bos_token_id = 0, decoder_start_token_id = 2
    # Config D: Greedy search (num_beams=1)
    # Config E: Beam search with repetition_penalty / no_repeat_ngram_size
    # Config F: Suppressing specific artifact tokens (e.g., bad_words_ids for '#')
    # Config G: Post-processing strip of leading markdown symbols

    hash_token_ids = [base_tok.encode('#', add_special_tokens=False)[0]]
    quote_token_ids = [base_tok.encode('"', add_special_tokens=False)[0]]
    bad_words_ids = [[t] for t in hash_token_ids + quote_token_ids]

    configs = {
        "Config_A_Eval_Default": {
            "decoder_start_token_id": 0,
            "num_beams": 4,
            "bad_words_ids": None,
            "early_stopping": True
        },
        "Config_B_Native_DecoderStart2": {
            "decoder_start_token_id": 2,
            "num_beams": 4,
            "bad_words_ids": None,
            "early_stopping": True
        },
        "Config_C_Greedy_Beam1": {
            "decoder_start_token_id": 2,
            "num_beams": 1,
            "bad_words_ids": None,
            "early_stopping": False
        },
        "Config_D_Suppressed_BadTokens": {
            "decoder_start_token_id": 2,
            "num_beams": 4,
            "bad_words_ids": bad_words_ids,
            "early_stopping": True
        },
        "Config_E_PostProcessed_Strip": {
            "decoder_start_token_id": 2,
            "num_beams": 4,
            "bad_words_ids": None,
            "early_stopping": True,
            "post_strip_md": True
        }
    }

    results = []

    for sample in samples:
        l_idx = sample["line_idx"]
        crop = sample["crop"]
        gt = sample["gt"]

        logger.info(f"\n==================== LINE {l_idx} ====================")
        logger.info(f"GT: {gt}")

        pv = processor(crop, return_tensors="pt").pixel_values.to(device)

        line_res = {"line_idx": l_idx, "gt": gt, "variants": {}}

        for cfg_name, cfg in configs.items():
            t0 = time.time()
            gen_kwargs = {
                "max_new_tokens": 96,
                "num_beams": cfg["num_beams"],
                "early_stopping": cfg.get("early_stopping", True),
                "return_dict_in_generate": True,
                "output_scores": False
            }
            if cfg.get("decoder_start_token_id") is not None:
                gen_kwargs["decoder_start_token_id"] = cfg["decoder_start_token_id"]
            if cfg.get("bad_words_ids") is not None:
                gen_kwargs["bad_words_ids"] = cfg["bad_words_ids"]

            with torch.no_grad():
                outputs = model.generate(pv, **gen_kwargs)

            raw_tokens = outputs.sequences[0].tolist()
            decoded_raw = processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0].strip()
            elapsed_ms = round((time.time() - t0) * 1000, 2)

            # Check post processing
            text_cleaned = normalize_text_syntax(decoded_raw)
            if cfg.get("post_strip_md"):
                # Strip leading markdown symbols (#, ##, *, -, quotes)
                import re
                text_cleaned = re.sub(r'^[#\s\"\'\.\-\*]+', '', text_cleaned).strip()
                text_cleaned = re.sub(r'\s*#\s*', ' ', text_cleaned)
                text_cleaned = re.sub(r'\.{2,}', '', text_cleaned).strip()

            cer = calculate_cer(gt, text_cleaned)
            wer = calculate_wer(gt, text_cleaned)

            first_5_tokens = [f"{tid}:'{base_tok.decode([tid])}'" for tid in raw_tokens[:6]]

            logger.info(f"[{cfg_name}] ({elapsed_ms}ms) CER={cer*100:.1f}% WER={wer*100:.1f}%")
            logger.info(f"   Raw text: '{decoded_raw}'")
            logger.info(f"   Cleaned:  '{text_cleaned}'")
            logger.info(f"   Tokens:   {first_5_tokens}")

            line_res["variants"][cfg_name] = {
                "elapsed_ms": elapsed_ms,
                "raw_text": decoded_raw,
                "cleaned_text": text_cleaned,
                "cer": round(cer, 4),
                "wer": round(wer, 4),
                "raw_token_ids": raw_tokens[:10]
            }

        results.append(line_res)

    out_path = os.path.join(backend_dir, "ocr_evaluation", "diagnostic_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nDiagnostic results saved to {out_path}")


if __name__ == "__main__":
    run_diagnostics()

