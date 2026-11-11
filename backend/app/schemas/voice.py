from pydantic import BaseModel, Field, field_validator
from app.core.config import settings


class VoiceTranscribeResponse(BaseModel):
    text: str
    language: str = "en"
    duration_seconds: float
    confidence: float | None = None
    engine: str
    model: str
    processing_time_ms: float


class VoiceSpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=settings.VOICE_TTS_MAX_CHARS)

    @field_validator("text")
    @classmethod
    def validate_text_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Speech text cannot be empty or whitespace only.")
        if len(cleaned) > settings.VOICE_TTS_MAX_CHARS:
            raise ValueError(
                f"Speech text exceeds maximum length of {settings.VOICE_TTS_MAX_CHARS} characters."
            )
        return cleaned

