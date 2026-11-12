from typing import Literal
from pydantic import BaseModel, Field


RecoveryDecision = Literal["UNCHANGED", "RECOVERED", "SUGGESTED", "AMBIGUOUS", "MANUAL"]


class VoiceQueryRecoverRequest(BaseModel):
    raw_transcript: str = Field(..., max_length=2000)
    document_id: int | None = None
    document_ids: list[int] | None = Field(default=None, max_length=20)
    manual_override: bool = False
    manually_edited_transcript: str | None = Field(default=None, max_length=2000)


class VoiceRecoverySuggestion(BaseModel):
    original_span: str
    suggested_span: str
    replacement_query: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    matched_documents: list[str] = Field(default_factory=list)


class VoiceRecoveryChange(BaseModel):
    original_span: str
    recovered_span: str
    change_type: str  # acronym, spaced_acronym, technical_term, spoken_number, spoken_punctuation, manual
    decision: RecoveryDecision
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    signals: dict[str, float] = Field(default_factory=dict)


class VoiceQueryRecoverResponse(BaseModel):
    raw_transcript: str
    recovered_transcript: str
    decision: RecoveryDecision
    recovery_applied: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    recovery_reason: str
    suggestions: list[VoiceRecoverySuggestion] = Field(default_factory=list)
    changes: list[VoiceRecoveryChange] = Field(default_factory=list)
    document_scope_count: int = 0
    cache_hit: bool = False
    processing_time_ms: float = 0.0

