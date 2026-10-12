from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ConversationMessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: Literal["user", "assistant"]
    content: str
    sources: list[dict] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationSummaryResponse(BaseModel):
    id: int
    title: str
    scope_mode: Literal["all", "specific"]
    selected_doc_ids: list[int] | None = None
    message_count: int = 0
    last_message_preview: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    id: int
    title: str
    scope_mode: Literal["all", "specific"]
    selected_doc_ids: list[int] | None = None
    messages: list[ConversationMessageResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    scope_mode: Literal["all", "specific"] = "all"
    selected_doc_ids: list[int] | None = Field(default=None, max_length=50)

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped or None
        return None


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    scope_mode: Literal["all", "specific"] | None = None
    selected_doc_ids: list[int] | None = Field(default=None, max_length=50)

    @field_validator("title")
    @classmethod
    def validate_title_non_empty(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Conversation title cannot be empty or whitespace only.")
            return stripped
        return None
