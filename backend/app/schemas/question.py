from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    query: str
    document_id: int | None = None
    document_ids: list[int] | None = Field(default=None, max_length=20)
    top_k: int = Field(default=5, ge=1, le=20)