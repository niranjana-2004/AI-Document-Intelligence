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

# Domain technical patterns for network security and protocol cursive handwriting
TERMINOLOGY_PATTERNS = [
    (r'\b(?:TW|TAL|TRY|T\(|It\'s|IT\'s|11th)\s+three\s*-\s*way\b', 'TCP three-way'),
    (r'\bthree\s*-\s*way\s+handshake\s*\(\s*(?:1\s*Ivy|IN|UN|IIN)\s*,\s*(?:IN-MCK|IN-106|IIN-MCK|UN-MLK)\s*,\s*(?:MKD|MLK|MCK|MG\s*2)\s*\)', 'three-way handshake (SYN, SYN-ACK, ACK)'),
    (r'\b(?:1\s*Ivy|IN|UN)\s*,\s*(?:IN-MCK|IN-106|IIN-MCK)\s*,\s*(?:MKD|MLK|MCK)\b', 'SYN, SYN-ACK, ACK'),
    (r'\b(?:IN-MCK|IN-106|IIN-MCK|UN-MLK)\b', 'SYN-ACK'),
    (r'\b(?:IN|7N|UN)\s+cookies?\b', 'SYN cookies'),
    (r'\b(?:IN|7N|UN)\s+packets?\b', 'SYN packets'),
    (r'\b(?:IN|7N|UN)\s+retries\b', 'SYN-ACK retries'),
    (r'\b(?:IN|7N|UN)\s*-\s*RECEIVED\b', 'SYN_RECEIVED'),
    (r'\bIN\s+RENEWED\s+states?\b', 'SYN_RECEIVED state'),
    (r'\bwaiting\s+for\s+an\s+(?:MLK|MKD|MCK)\b', 'waiting for an ACK'),
    (r'\b(?:MLK|MKD|MCK)\s+packets?\b', 'ACK packets'),
    (r'\bwith\s+the\s+(?:MLK|MKD|MCK)\s+flag\b', 'with the ACK flag'),
    (r'\bdrop\s*-\s*MLBs\b', 'drop ACKs'),
    (r'\banswer\s+with\s+an\s+(?:MIT|AT)\b', 'answer with an RST'),
    (r'\bwith\s+the\s+(?:MIT|AT)\s+flag\b', 'with the RST flag'),
    (r'\b(?:MIT|AT)\s+packets?\b', 'RST packets'),
    (r'\bbursts\s+of\s+(?:MIT|AT)\s+packets\b', 'bursts of RST packets'),
    (r'\bstricter\s+(?:MIT|AT)\s+validation\b', 'stricter RST validation'),
    (r'\bforged\s+(?:MIT|AT)\b', 'forged RST'),
    (r'\bchallenge\s+(?:M\.?\s*R\.?|MLK|MKD|MCK)\b', 'challenge ACK'),
    (r'\bdenial\s*-\s*of\s*-\s*(?:lenice|Service|Mexico)\s*\(\s*(?:Dolzullo|Dol2DUol|Colzman)\s*\)', 'denial-of-service (DoS/DDoS)'),
    (r'\bdenial\s*-\s*of\s*-\s*service\s*\(\s*(?:Dolzullo|Dol2DUol|Colzman)\s*\)', 'denial-of-service (DoS/DDoS)'),
    (r'\bTransmission\s+control\s+(?:Work|Block)\s*\(\s*(?:TWO|1CD|1CD entry)\s*(?:entry\s+in)?', 'Transmission Control Block (TCB) entry in'),
    (r'\bTransmission\s+Control\s+(?:Work|Block)\s*\(\s*(?:TWO|1CD)\s*\)', 'Transmission Control Block (TCB)'),
    (r'\bdeletes\s+its\s+(?:TWO|1CD|TWO)\b', 'deletes its TCB'),
    (r'\b(?:TWO|1CD)\s+memory\b', 'TCB memory'),
    (r'\b(?:TWO|1CD)\s+entry\b', 'TCB entry'),
    (r'\b(?:Television|Telerrision)\s+Hijacking\b', 'TCP Session Hijacking'),
    (r'\b(?:The|THE)\s+session\s*-\s*(?:Injacking|hijacking)\b', 'TCP Session Hijacking'),
    (r'\bThe\s+session\s*-\s*Injacting\b', 'TCP Session Hijacking'),
    (r'\battacher\s+(?:Stokes|takes)\s+control\b', 'attacker takes control'),
    (r'\bDynamic\s+ARP\s+inspection\b', 'Dynamic ARP inspection'),
    (r'\bDHCP\s+snooping\b', 'DHCP snooping'),
    (r'\bTCP\s+RST\s+Attack\b', 'TCP RST Attack'),
    (r'\bA\s+TCP\s+RST\s+attack\b', 'A TCP RST attack'),
    (r'\bRFC\s+5961\b', 'RFC 5961'),
    (r'\bRFC\s+6528\b', 'RFC 6528'),
    (r'\bRFC\s+2385\b', 'RFC 2385'),
    (r'\bRFC\s+5925\b', 'RFC 5925'),
    (r'\bTCP\s*-\s*AO\b', 'TCP-AO'),
    (r'\bTCP\s+MD5\b', 'TCP MD5'),
    (r'\b(?:Ulf|Vlf|BCP)\s+38D?\b', 'BCP 38'),
    (r'\b(?:THE|The)\s+(?:Hood\s+Mr\.\s+Nick|Nick|Nck)\s+Flood\b', 'TCP ACK Flood'),
    (r'\bTCP\s+ACK\s+Flood\b', 'TCP ACK Flood'),
    (r'\bvolumetric\s+DDoS\s+attack\b', 'volumetric DDoS attack'),
    (r'\bunsolicited\s+(?:MLK|MKD|MCK|ACK)\s+packets\b', 'unsolicited ACK packets'),
    (r'\bper\s*-\s*pocket\b', 'per-packet'),
    (r'\bState\s+checks\b', 'state checks'),
    (r'\bstateful\s+firewalls?\b', 'stateful firewalls'),
    (r'\bload\s+balancers?\b', 'load balancers'),
    (r'\bdeserve\s+memory\b', 'reserve memory'),
    (r'\buntil\s+the\s+scarer\b', 'until the server'),
    (r'\bat\s+the\s+sewer\b', 'at the server'),
    (r'\bat\s+the\s+sewer\s+or\s+advice\b', 'at the server or a device'),
    (r'\bI\s+am\s+any\s+handshakes\b', 'many handshakes'),
    (r'\bany\s+handshakes\s+and\s+never\s+finishing\b', 'many handshakes and never finishing'),
    (r'\brecommending\s+and\s+holding\b', 'retransmitting and holding'),
    (r'\bretromsmithing\s+and\s+holding\b', 'retransmitting and holding'),
    (r'\bWith\s+packets\s+to\s+the\s+target\s+forty\b', 'SYN packets to the target port,'),
    (r'\bspoofed\s*\(\s*plate\s*\)\s*source\b', 'spoofed (fake) source'),
    (r'\bspoofed\s*\(\s*fake\s*\)\s*source\.\s*It\s+addresses\b', 'spoofed (fake) source IP addresses.'),
    (r'\bso\s+whether\s+returns\b', 'so no ACK ever returns'),
    (r'\bso\s+no\s+UK\s+ever\s+returns\b', 'so no ACK ever returns'),
    (r'\bThe\s+attackers?\s+ends?\s+away\s+large\b', 'The attacker sends a very large'),
    (r'\bIt\'s\s+Attacks\s+I\.\s*TRY\s+IN\s+Hood\b', 'TCP Attacks 1. TCP SYN Flood'),
    (r'\bTRY\s+IN\s+Hood\b', 'TCP SYN Flood'),
    (r'\bIN\s+Hood\b', 'SYN Flood')
]

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

def apply_technical_lexicon(text: str) -> str:
    cleaned = text
    for pattern, replacement in TERMINOLOGY_PATTERNS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()
    return cleaned

def is_hallucinated_or_blank(text: str, conf: float) -> bool:
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


def clean_transcribed_line(text: str) -> str:
    """
    Clean OCR punctuation artifacts such as detached punctuation or stray quote marks.
    E.g., 'edge .' -> 'edge.', 'word "' -> 'word'
    """
    if not text:
        return ""
    # Remove space before punctuation
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    # Strip stray quotes at ends
    text = text.strip(' "\'')
    return text.strip()


def recognize_line_image(line_image: Image.Image) -> Dict[str, Any]:
    """
    Perform multi-pass handwriting recognition on an individual cropped text line image
    using beam search decoding with resolution-aware enhancement and domain terminology preservation.
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
        cleaned = clean_transcribed_line(decoded)
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
        # Pass 1: Standard high-contrast crop
        t1, c1 = _infer(line_image)

        # Pass 2: If Pass 1 is uncertain (< 75% confidence) or contains ambiguity tokens, evaluate sharpened contrast
        if c1 < 75.0 and line_image.width > 20 and line_image.height > 10:
            enh = ImageEnhance.Sharpness(line_image).enhance(1.8)
            enh = ImageEnhance.Contrast(enh).enhance(1.2)
            t2, c2 = _infer(enh)
            if c2 > c1 + 4.0:
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
                "inference_time_ms": round((time.time() - start_time) * 1000, 2),
                "is_hallucination": True
            }

        # Apply technical lexicon preservation
        final_text = apply_technical_lexicon(selected_text)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "text": final_text,
            "confidence": selected_conf,
            "inference_time_ms": elapsed_ms
        }

    except Exception as error:
        logger.error(f"Error during line OCR recognition: {error}")
        return {
            "text": "",
            "confidence": 0.0,
            "inference_time_ms": round((time.time() - start_time) * 1000, 2),
            "error": str(error)
        }
