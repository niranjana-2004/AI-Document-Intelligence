import threading
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.voice import VoiceSpeakRequest, VoiceTranscribeResponse
from app.services.tts_service import (
    TTSServiceError,
    TTSValidationError,
    synthesize_speech_wav,
)
from app.services.voice_service import (
    VoiceTranscriptionError,
    VoiceValidationError,
    transcribe_audio_bytes,
)

router = APIRouter(
    prefix="/voice",
    tags=["Voice Assistant"],
)


@router.post("/transcribe", response_model=VoiceTranscribeResponse)
async def transcribe_voice_endpoint(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Transcribe authenticated user's uploaded microphone recording using the
    fully local faster-whisper STT engine. Temporary audio is discarded immediately.
    """
    _ = current_user.id  # Enforce active authenticated user record

    max_read = settings.VOICE_MAX_AUDIO_BYTES + 1
    try:
        audio_bytes = await audio.read(max_read)
    finally:
        await audio.close()

    try:
        result = await run_in_threadpool(
            transcribe_audio_bytes,
            audio_bytes,
            audio.filename,
            audio.content_type,
        )
        return VoiceTranscribeResponse(**result)
    except VoiceValidationError as ve:
        raise HTTPException(status_code=ve.status_code, detail=str(ve))
    except VoiceTranscriptionError as te:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(te),
        )


@router.post("/speak")
async def speak_text_endpoint(
    payload: VoiceSpeakRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Synthesize grounded answer text into WAV speech locally via Piper TTS.
    Requires JWT authentication and never stores audio permanently.
    """
    _ = current_user.id
    cancel_event = threading.Event()
    try:
        result = await run_in_threadpool(
            synthesize_speech_wav,
            payload.text,
            cancel_event,
        )
    except TTSValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except TTSServiceError as te:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(te),
        )

    return Response(
        content=result["audio_bytes"],
        media_type=result["media_type"],
        headers={
            "Cache-Control": "no-store",
            "X-TTS-Engine": result["engine"],
            "X-TTS-Model": result["model"],
            "X-TTS-Processing-Ms": str(result["processing_time_ms"]),
        },
    )

