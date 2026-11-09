from typing import List, Optional
from pydantic import BaseModel, Field


class ComparisonRequest(BaseModel):
    document_a_id: int = Field(..., description="ID of primary baseline document (Document A)")
    document_b_id: int = Field(..., description="ID of comparison document (Document B)")
    force_refresh: bool = Field(default=False, description="Bypass cache and force re-comparison")


class DocumentMeta(BaseModel):
    id: int
    filename: str
    document_type: str
    is_handwritten: bool = False
    total_pages: int = 1
    chunk_count: int = 0


class ComparisonStatistics(BaseModel):
    total_units: int = 0
    similar: int = 0
    modified: int = 0
    added: int = 0
    removed: int = 0


class SimilarityItem(BaseModel):
    id: str
    title: str
    category: Optional[str] = "General"
    document_a_text: str
    document_b_text: str
    document_a_page: int = 1
    document_b_page: int = 1
    similarity_score: float = 1.0
    is_unchanged: bool = False


class ModifiedItem(BaseModel):
    id: str
    title: str
    category: Optional[str] = "General"
    change_description: str
    document_a_text: str
    document_b_text: str
    document_a_page: int = 1
    document_b_page: int = 1
    similarity_score: float


class AddedItem(BaseModel):
    id: str
    title: str
    category: Optional[str] = "General"
    document_b_text: str
    document_b_page: int = 1


class RemovedItem(BaseModel):
    id: str
    title: str
    category: Optional[str] = "General"
    document_a_text: str
    document_a_page: int = 1


class ComparisonResponse(BaseModel):
    document_a: DocumentMeta
    document_b: DocumentMeta
    summary: str
    key_changes: List[str] = []
    important_additions: List[str] = []
    important_removals: List[str] = []
    implications: str = ""
    statistics: ComparisonStatistics
    similarities: List[SimilarityItem] = []
    modified: List[ModifiedItem] = []
    added: List[AddedItem] = []
    removed: List[RemovedItem] = []
    cached: bool = False

