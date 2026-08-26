from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    query: str
    document_id: int | None = None
    top_k: int = Field(default=5, ge=1, le=20)