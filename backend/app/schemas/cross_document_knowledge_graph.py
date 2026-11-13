from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

CROSS_DOCUMENT_GRAPH_VERSION = "cdkg-v1"


class CrossDocumentGraphGenerateRequest(BaseModel):
    document_ids: List[int] = Field(default_factory=list, description="List of document IDs to analyze together")
    force_refresh: bool = False
    include_low_confidence: bool = False
    skip_llm: bool = False
    max_nodes: int = Field(default=60, ge=6, le=120)
    only_shared: bool = False


class DocumentOccurrenceSummary(BaseModel):
    document_id: int
    document_name: str
    occurrences: int = 1
    source_pages: List[int] = Field(default_factory=list)


class EntityOccurrenceOut(BaseModel):
    id: Optional[int] = None
    document_id: int
    document_name: str
    chunk_id: Optional[int] = None
    page_number: int = 1
    original_label: str
    source_text: str
    resolution_confidence: float = 0.90
    resolution_method: str = "exact_match"
    evidence: Dict[str, Any] = Field(default_factory=dict)


class CanonicalEntityOut(BaseModel):
    id: Optional[int] = None
    entity_key: str
    canonical_name: str
    normalized_name: str
    entity_type: str = "Concept"
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    confidence: float = 0.85
    confidence_tier: str = "high"
    importance_score: float = 0.5
    document_count: int = 1
    occurrence_count: int = 1
    is_shared: bool = False
    documents: List[DocumentOccurrenceSummary] = Field(default_factory=list)
    occurrences: List[EntityOccurrenceOut] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CrossDocumentEdgeOut(BaseModel):
    id: Optional[int] = None
    source_key: str
    target_key: str
    relationship: str
    origin: str = "explicit"
    confidence: float = 0.75
    confidence_tier: str = "high"
    confidence_breakdown: Dict[str, float] = Field(default_factory=dict)
    evidence_count: int = 1
    supporting_document_ids: List[int] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: Optional[str] = None
    is_cross_document: bool = False


class CrossDocumentGraphStats(BaseModel):
    total_entities: int = 0
    shared_entities: int = 0
    document_specific_entities: int = 0
    total_edges: int = 0
    cross_document_edges: int = 0
    documents_selected: int = 0
    entity_type_counts: Dict[str, int] = Field(default_factory=dict)
    relationship_counts: Dict[str, int] = Field(default_factory=dict)
    average_confidence: float = 0.0
    grounded_edge_ratio: float = 1.0


class SelectedDocumentInfo(BaseModel):
    document_id: int
    title: str
    filename: str
    document_type: str
    page_count: int = 1
    is_handwritten: bool = False


class CrossDocumentKnowledgeGraphResponse(BaseModel):
    id: int
    collection_hash: str
    selected_document_ids: List[int] = Field(default_factory=list)
    selected_documents: List[SelectedDocumentInfo] = Field(default_factory=list)
    graph_version: str = CROSS_DOCUMENT_GRAPH_VERSION
    status: str = "ready"
    generation_method: str = "hybrid"
    cached: bool = False
    is_outdated: bool = False
    stats: CrossDocumentGraphStats
    entities: List[CanonicalEntityOut] = Field(default_factory=list)
    edges: List[CrossDocumentEdgeOut] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CrossDocumentGraphDeleteResponse(BaseModel):
    graph_id: int
    deleted: bool
    message: str

