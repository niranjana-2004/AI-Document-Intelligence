from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message content cannot be empty or whitespace only.")
        return stripped


class ConversationalQuery(str):
    """
    String subclass carrying optional conversation_history metadata,
    allowing transparent backward-compatibility with string consumers.
    """
    conversation_history: list[ChatMessage] | None = None

    def __new__(cls, content: str, conversation_history: list[ChatMessage] | None = None):
        instance = super().__new__(cls, content)
        instance.conversation_history = conversation_history
        return instance


class QuestionRequest(BaseModel):
    query: str
    document_id: int | None = None
    document_ids: list[int] | None = Field(default=None, max_length=20)
    top_k: int = Field(default=5, ge=1, le=20)
    conversation_history: list[ChatMessage] | None = Field(default=None, max_length=6)
    conversation_id: int | None = None

    @field_validator("conversation_history")
    @classmethod
    def validate_total_history_length(cls, history: list[ChatMessage] | None) -> list[ChatMessage] | None:
        if history is None:
            return None
        total_len = sum(len(msg.content) for msg in history)
        if total_len > 6000:
            raise ValueError("Total conversation history length exceeds limit of 6000 characters.")
        return history

    @model_validator(mode="after")
    def wrap_query_with_history(self):
        if self.conversation_history is not None:
            self.query = ConversationalQuery(self.query, self.conversation_history)
        return self


class SuggestedQuestionsRequest(BaseModel):
    document_ids: list[int] | None = Field(default=None, max_length=20)


class SuggestedQuestionsResponse(BaseModel):
    questions: list[str]
    scope: Literal["all", "specific"]
