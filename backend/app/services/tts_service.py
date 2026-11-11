import io
import logging
import re
import threading
import time
import wave
from pathlib import Path
from typing import Tuple

from piper.voice import PiperVoice

from app.core.config import settings

logger = logging.getLogger(__name__)

_piper_voice: PiperVoice | None = None
_piper_lock = threading.Lock()


class TTSValidationError(ValueError):
    """Raised when requested speech text is empty or exceeds configured limits."""


class TTSServiceError(RuntimeError):
    """Raised when the local TTS engine is missing or fails to synthesize audio."""


def prepare_text_for_speech(raw_text: str) -> str:
    """
    Clean markdown formatting and bracketed citation markers ([1], [2, 3], [Source N | ...])
    so grounded answers read naturally aloud without changing the visible chat text.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    text = raw_text
    # Remove full source attribution tags like [Source 1 | Document: ... | Page: 2]
    text = re.sub(r"\[Source\s+\d+\s*\|[^\]]+\]", "", text, flags=re.IGNORECASE)
    # Remove inline numeric citations like [1] or [1, 2]
    text = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", text)
    # Convert markdown links [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Strip markdown headings, bold/italic markers, code ticks, and list prefixes
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^\s*[-*•]\s+", "", text)
    text = re.sub(r"[`*_~]+", "", text)
    # Normalize spaces cleanly before punctuation
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _resolve_piper_model_paths() -> Tuple[Path, Path]:
    piper_dir = Path(settings.VOICE_MODELS_DIR) / "piper"
    voice_name = settings.VOICE_TTS_MODEL.strip()
    onnx_path = piper_dir / f"{voice_name}.onnx"
    config_path = piper_dir / f"{voice_name}.onnx.json"
    return onnx_path, config_path


def get_piper_voice() -> PiperVoice:
    """Lazily initialize and cache the local CPU Piper ONNX voice thread-safely."""
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice

    with _piper_lock:
        if _piper_voice is None:
            onnx_path, config_path = _resolve_piper_model_paths()
            if (
                not onnx_path.exists()
                or onnx_path.stat().st_size == 0
                or not config_path.exists()
                or config_path.stat().st_size == 0
            ):
                raise TTSServiceError(
                    f"Local Piper voice model '{settings.VOICE_TTS_MODEL}' is not available."
                )
            try:
                _piper_voice = PiperVoice.load(
                    model_path=onnx_path,
                    config_path=config_path,
                    use_cuda=False,
                )
            except Exception as exc:
                logger.exception("Failed to load Piper TTS voice model")
                raise TTSServiceError("Local TTS voice failed to initialize.") from exc
    return _piper_voice


def synthesize_speech_wav(
    text: str,
    cancel_event: threading.Event | None = None,
) -> dict:
    """
    Synthesize grounded answer text into an in-memory 16-bit mono WAV payload
    using local Piper TTS without persisting generated audio to disk.
    """
    if not isinstance(text, str) or not text.strip():
        raise TTSValidationError("Text to speak cannot be empty.")

    if len(text.strip()) > settings.VOICE_TTS_MAX_CHARS:
        raise TTSValidationError(
            f"Text exceeds maximum speech limit of {settings.VOICE_TTS_MAX_CHARS} characters."
        )

    spoken_text = prepare_text_for_speech(text)
    if not spoken_text:
        raise TTSValidationError("No speakable text remains after formatting cleanup.")

    if cancel_event and cancel_event.is_set():
        raise TTSServiceError("Speech synthesis cancelled.")

    t0 = time.perf_counter()
    voice = get_piper_voice()

    wav_buffer = io.BytesIO()
    try:
        with wave.open(wav_buffer, "wb") as wav_file:
            voice.synthesize_wav(spoken_text, wav_file)

        if cancel_event and cancel_event.is_set():
            raise TTSServiceError("Speech synthesis cancelled.")

        wav_bytes = wav_buffer.getvalue()
    except TTSServiceError:
        raise
    except Exception as exc:
        logger.exception("Local Piper synthesis failed")
        raise TTSServiceError("Voice playback isn't available right now.") from exc
    finally:
        wav_buffer.close()

    if not wav_bytes or len(wav_bytes) <= 44:
        raise TTSServiceError("Local TTS produced empty audio output.")

    processing_time_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    return {
        "audio_bytes": wav_bytes,
        "media_type": "audio/wav",
        "engine": "piper",
        "model": settings.VOICE_TTS_MODEL,
        "spoken_char_count": len(spoken_text),
        "processing_time_ms": processing_time_ms,
    }

