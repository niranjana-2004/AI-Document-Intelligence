from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.cross_document_knowledge_graph import SelectedDocumentInfo

KNOWLEDGE_INTELLIGENCE_VERSION = "ki-v1"


class KnowledgeIntelligenceQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000, description="User question or exploration query")
    document_ids: List[int] = Field(default_factory=list, description="List of document IDs to scope the query to")
    focus_entity: Optional[str] = Field(default=None, description="Optional entity key to focus or drill down on")
    force_refresh: bool = Field(default=False, description="Bypass cache and force regeneration")
    include_low_confidence: bool = Field(default=False, description="Whether to include low-confidence entities/relationships")
    skip_llm: bool = Field(default=False, description="Deterministic synthesis only without LLM")
    max_evidence_items: int = Field(default=20, ge=3, le=50, description="Max evidence excerpts to retrieve")


class DirectAnswer(BaseModel):
    text: str
    confidence: float = 0.85
    grounding_status: Literal["grounded", "partial", "insufficient_evidence"] = "grounded"
    supporting_sources: List[str] = Field(default_factory=list)
    synthesis_method: str = "ollama"  # or 'deterministic_fallback'


class KnowledgeOverviewItem(BaseModel):
    canonical_name: str
    entity_key: str
    entity_type: str = "Concept"
    document_count: int = 1
    mention_count: int = 1
    is_shared: bool = False
    documents: List[str] = Field(default_factory=list)
    document_ids: List[int] = Field(default_factory=list)
    importance_score: float = 0.5


class IntelligenceRelationship(BaseModel):
    source_entity: str
    target_entity: str
    predicate: str
    confidence: float = 0.75
    supporting_documents: List[str] = Field(default_factory=list)
    supporting_document_ids: List[int] = Field(default_factory=list)
    evidence_snippets: List[str] = Field(default_factory=list)
    is_cross_document: bool = False


class IntelligenceEvidenceItem(BaseModel):
    id: str
    document_id: int
    document_title: str
    page_number: int = 1
    chunk_id: Optional[int] = None
    source_type: Literal["printed_pdf", "handwritten", "research_paper", "text_document", "document_chunk"] = "document_chunk"
    excerpt: str
    entity: str
    relationship: Optional[str] = None
    confidence: float = 0.90
    section: Optional[str] = None


class CrossDocumentInsight(BaseModel):
    entity: str
    insight_type: Literal["shared_knowledge", "document_specific", "synthesis", "comparison"] = "shared_knowledge"
    description: str
    document_names: List[str] = Field(default_factory=list)
    confidence: float = 0.85


class ConflictItem(BaseModel):
    entity: str
    category: Literal["agreement", "different_emphasis", "different_definition", "contradiction", "insufficient_evidence"] = "agreement"
    description: str
    claim_a: Dict[str, Any] = Field(default_factory=dict)
    claim_b: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.75


class RelatedTopicItem(BaseModel):
    name: str
    entity_key: str
    relationship_to_focus: str
    document_count: int = 1


class KnowledgeIntelligenceResponse(BaseModel):
    query: str
    normalized_query: str
    intent: str = "knowledge_lookup"
    focus_entities: List[str] = Field(default_factory=list)
    selected_document_ids: List[int] = Field(default_factory=list)
    selected_documents: List[SelectedDocumentInfo] = Field(default_factory=list)
    direct_answer: DirectAnswer
    knowledge_overview: List[KnowledgeOverviewItem] = Field(default_factory=list)
    relationships: List[IntelligenceRelationship] = Field(default_factory=list)
    evidence: List[IntelligenceEvidenceItem] = Field(default_factory=list)
    cross_document_insights: List[CrossDocumentInsight] = Field(default_factory=list)
    conflicts: List[ConflictItem] = Field(default_factory=list)
    related_topics: List[RelatedTopicItem] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    cached: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
