import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import av
import numpy as np
from faster_whisper import WhisperModel

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_MIME_TYPES = {
    "audio/webm",
    "video/webm",
    "audio/ogg",
    "application/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
}

ALLOWED_AUDIO_EXTENSIONS = {
    ".webm",
    ".ogg",
    ".wav",
    ".mp4",
    ".m4a",
    ".mp3",
    ".mpeg",
    ".flac",
}

MIME_TO_EXTENSION = {
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/ogg": ".ogg",
    "application/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mp4": ".mp4",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/flac": ".flac",
}

_whisper_model: WhisperModel | None = None
_whisper_lock = threading.Lock()


class VoiceValidationError(ValueError):
    """Raised when uploaded audio fails validation before or after decoding."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class VoiceTranscriptionError(RuntimeError):
    """Raised when local STT model loading or inference fails."""


def normalize_mime_type(content_type: str | None) -> str:
    """Strip codec parameters from MIME string (e.g. 'audio/webm;codecs=opus' -> 'audio/webm')."""
    if not content_type:
        return ""
    return content_type.split(";")[0].strip().lower()


def validate_audio_upload(
    filename: str | None,
    content_type: str | None,
    audio_bytes: bytes,
) -> str:
    """
    Validate uploaded microphone audio bytes, size limits, and format.
    Returns a safe temporary file extension (e.g. '.webm' or '.wav').
    """
    if not audio_bytes:
        raise VoiceValidationError(
            "Recorded audio is empty. No speech detected.",
            status_code=400,
        )

    if len(audio_bytes) > settings.VOICE_MAX_AUDIO_BYTES:
        max_mb = round(settings.VOICE_MAX_AUDIO_BYTES / (1024 * 1024), 1)
        raise VoiceValidationError(
            f"Audio recording exceeds maximum allowed size of {max_mb} MB.",
            status_code=413,
        )

    base_mime = normalize_mime_type(content_type)
    safe_name = Path(filename or "recording").name
    ext = Path(safe_name).suffix.lower()

    mime_ok = base_mime in ALLOWED_AUDIO_MIME_TYPES
    ext_ok = ext in ALLOWED_AUDIO_EXTENSIONS

    if base_mime and not mime_ok and base_mime != "application/octet-stream":
        raise VoiceValidationError(
            f"Unsupported audio format '{base_mime}'. Allowed formats: WebM, OGG, WAV, MP4, MP3.",
            status_code=415,
        )

    if not mime_ok and not ext_ok:
        raise VoiceValidationError(
            "Unsupported or unrecognized audio file format. Allowed formats: WebM, OGG, WAV, MP4, MP3.",
            status_code=415,
        )

    return ext if ext_ok else MIME_TO_EXTENSION.get(base_mime, ".webm")


def get_whisper_model() -> WhisperModel:
    """Lazily initialize and cache the local CPU faster-whisper model thread-safely."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    with _whisper_lock:
        if _whisper_model is None:
            try:
                cpu_threads = max(1, min(os.cpu_count() or 4, 8))
                _whisper_model = WhisperModel(
                    settings.VOICE_STT_MODEL,
                    device="cpu",
                    compute_type=settings.VOICE_STT_COMPUTE_TYPE,
                    cpu_threads=cpu_threads,
                )
            except Exception as exc:
                logger.exception("Failed to initialize local faster-whisper model")
                raise VoiceTranscriptionError(
                    "Local speech recognition engine failed to initialize."
                ) from exc
    return _whisper_model


def _transcribe_file_with_model(tmp_path: str) -> dict[str, Any]:
    """Decode audio via PyAV, validate duration/energy, and run local Whisper transcription."""
    try:
        audio_array = decode_audio(tmp_path, sampling_rate=16000)
    except Exception as exc:
        raise VoiceValidationError(
            "Could not decode uploaded audio recording. Please try recording again.",
            status_code=400,
        ) from exc

    if audio_array is None or len(audio_array) == 0:
        raise VoiceValidationError("No speech detected. Please try again.", status_code=422)

    duration_seconds = round(float(len(audio_array)) / 16000.0, 2)
    if duration_seconds < 0.25:
        raise VoiceValidationError("Recording is too short. Please speak clearly and try again.", status_code=422)

    if duration_seconds > settings.VOICE_MAX_DURATION_SECONDS:
        raise VoiceValidationError(
            f"Recording duration ({duration_seconds}s) exceeds maximum limit of {int(settings.VOICE_MAX_DURATION_SECONDS)}s.",
            status_code=400,
        )

    rms = float(np.sqrt(np.mean(np.square(audio_array))))
    if rms < 1e-4:
        raise VoiceValidationError("No speech detected. Please try again.", status_code=422)

    model = get_whisper_model()
    try:
        segments, info = model.transcribe(
            audio_array,
            language="en",
            beam_size=2,
            vad_filter=True,
            initial_prompt=(
                "Academic and technical discussion: TCP, UDP, SYN flood, HTTP, CephVault, "
                "OCR, SQLite, FastAPI, neural networks."
            ),
        )
        text = " ".join(seg.text.strip() for seg in segments if seg.text).strip()
    except Exception as exc:
        logger.exception("Local faster-whisper transcription error")
        raise VoiceTranscriptionError(
            "Local speech recognition could not process the recording."
        ) from exc

    if not text:
        raise VoiceValidationError("No speech detected. Please try again.", status_code=422)

    return {
        "text": text,
        "language": getattr(info, "language", None) or "en",
        "duration_seconds": duration_seconds,
        "confidence": None,
        "engine": "faster-whisper",
        "model": settings.VOICE_STT_MODEL,
    }


def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    """
    Validate uploaded audio bytes, materialize a short-lived temporary file for
    container decoding, transcribe locally using faster-whisper, and strictly
    delete temporary audio on both success and failure.
    """
    t0 = time.perf_counter()
    safe_ext = validate_audio_upload(filename, content_type, audio_bytes)

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=safe_ext,
            prefix="cognidocs_stt_",
        ) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        result = _transcribe_file_with_model(tmp_path)
        result["processing_time_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        return result
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError as cleanup_err:
                logger.warning("Failed to delete temp STT file %s: %s", tmp_path, cleanup_err)

