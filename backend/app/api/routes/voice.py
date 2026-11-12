import json
import threading
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.voice import VoiceSpeakRequest, VoiceTranscribeResponse
from app.schemas.voice_query_recovery import (
    VoiceQueryRecoverRequest,
    VoiceQueryRecoverResponse,
)
from app.services.tts_service import (
    TTSServiceError,
    TTSValidationError,
    synthesize_speech_wav,
)
from app.services.voice_query_recovery_service import recover_voice_query
from app.services.voice_service import (
    VoiceTranscriptionError,
    VoiceValidationError,
    transcribe_audio_bytes,
)
from app.services.voice_terminology_service import build_whisper_initial_prompt

router = APIRouter(
    prefix="/voice",
    tags=["Voice Assistant"],
)


def _parse_document_ids_form(raw_value: str | None) -> list[int] | None:
    if raw_value is None:
        return None
    stripped = raw_value.strip()
    if not stripped:
        return None
    try:
        if stripped.startswith("["):
            parsed = json.loads(stripped)
            if not isinstance(parsed, list):
                raise ValueError("document_ids must be a list of positive integers.")
            ids = [int(item) for item in parsed]
        else:
            ids = [int(part.strip()) for part in stripped.split(",") if part.strip()]
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid document_ids scope filter.",
        ) from exc

    if any(doc_id <= 0 for doc_id in ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document IDs must be positive integers.",
        )
    return ids or None


@router.post("/transcribe", response_model=VoiceTranscribeResponse)
async def transcribe_voice_endpoint(
    audio: UploadFile = File(...),
    document_id: int | None = Form(None),
    document_ids: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Transcribe authenticated user's uploaded microphone recording using the
    fully local faster-whisper STT engine, dynamically anchored with terminology
    from the user's currently scoped documents. Temporary audio is discarded immediately.
    """
    parsed_doc_ids = _parse_document_ids_form(document_ids)
    initial_prompt = build_whisper_initial_prompt(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        document_ids=parsed_doc_ids,
    )

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
            initial_prompt,
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


@router.post("/recover-query", response_model=VoiceQueryRecoverResponse)
def recover_voice_query_endpoint(
    payload: VoiceQueryRecoverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluate raw voice STT transcript against authenticated user's selected
    document terminology using context-aware safety-gated query recovery.
    Never modifies manual user edits or leaks terminology across tenants/documents.
    """
    return recover_voice_query(
        raw_transcript=payload.raw_transcript,
        db=db,
        user_id=current_user.id,
        document_id=payload.document_id,
        document_ids=payload.document_ids,
        manual_override=payload.manual_override,
        manually_edited_transcript=payload.manually_edited_transcript,
    )


