from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


GRAPH_VERSION = "kg-v1"

ALLOWED_NODE_TYPES = (
    "Concept",
    "Entity",
    "Method",
    "Model",
    "System",
    "Dataset",
    "Metric",
    "Person",
    "Organization",
    "Attack",
    "Protocol",
    "Defense",
    "Problem",
    "Result",
    "Limitation",
    "FutureWork",
    "Section",
)

ALLOWED_RELATIONSHIPS = (
    "contains",
    "related_to",
    "depends_on",
    "causes",
    "results_in",
    "uses",
    "implements",
    "extends",
    "part_of",
    "example_of",
    "defined_by",
    "measured_by",
    "evaluated_on",
    "compared_with",
    "improves",
    "degrades",
    "supports",
    "contradicts",
    "precedes",
    "follows",
)

RELATIONSHIP_ALIAS_MAP: Dict[str, str] = {
    # Canonical identity
    **{rel: rel for rel in ALLOWED_RELATIONSHIPS},
    # Causal / exploitation / attack aliases
    "exploits": "depends_on",
    "abuses": "depends_on",
    "targets": "depends_on",
    "triggers": "causes",
    "induces": "causes",
    "leads_to": "results_in",
    "produces": "results_in",
    "generates": "results_in",
    "exhausts": "degrades",
    "disrupts": "degrades",
    "overwhelms": "degrades",
    "weakens": "degrades",
    "reduces": "degrades",
    "mitigates": "contradicts",
    "prevents": "contradicts",
    "defends_against": "contradicts",
    "protects_against": "contradicts",
    "blocks": "contradicts",
    # Structural / compositional / taxonomic
    "includes": "contains",
    "has_part": "contains",
    "comprises": "contains",
    "belongs_to": "part_of",
    "component_of": "part_of",
    "step_in": "part_of",
    "stage_of": "part_of",
    "is_a": "example_of",
    "type_of": "example_of",
    "kind_of": "example_of",
    "instance_of": "example_of",
    "defined_as": "defined_by",
    "characterized_by": "defined_by",
    # Technical / research / methodology
    "utilizes": "uses",
    "applies": "uses",
    "employs": "uses",
    "relies_on": "depends_on",
    "requires": "depends_on",
    "needs": "depends_on",
    "realizes": "implements",
    "encodes": "implements",
    "builds_on": "extends",
    "enhances": "improves",
    "outperforms": "improves",
    "solves": "improves",
    "addresses": "improves",
    "assessed_by": "measured_by",
    "quantified_by": "measured_by",
    "tested_on": "evaluated_on",
    "benchmarked_on": "evaluated_on",
    "trained_on": "evaluated_on",
    "validated_on": "evaluated_on",
    "contrasted_with": "compared_with",
    "versus": "compared_with",
    "backs": "supports",
    "validates": "supports",
    "confirms": "supports",
    "before": "precedes",
    "after": "follows",
    "associated_with": "related_to",
}

NodeOriginType = Literal["explicit", "derived", "inferred"]
ConfidenceTierType = Literal["high", "medium", "low"]


def normalize_relationship(raw_relationship: Optional[str]) -> Optional[str]:
    """Map an arbitrary or aliased predicate onto the controlled 20-verb vocabulary."""
    if not raw_relationship:
        return None
    cleaned = raw_relationship.strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")
    return RELATIONSHIP_ALIAS_MAP.get(cleaned)


def confidence_to_tier(confidence: float) -> ConfidenceTierType:
    """Classify numeric confidence into UI tiers (`high`, `medium`, `low`)."""
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.50:
        return "medium"
    return "low"


class KnowledgeGraphGenerateRequest(BaseModel):
    force_refresh: bool = False
    include_low_confidence: bool = False
    skip_llm: bool = False
    max_nodes: int = Field(default=32, ge=6, le=60)


class EvidenceRef(BaseModel):
    chunk_id: Optional[int] = None
    page: int = 1
    section: Optional[str] = None
    excerpt: str


class ConfidenceBreakdown(BaseModel):
    evidence_count_score: float = 0.0
    proximity_score: float = 0.0
    explicitness_score: float = 0.0
    semantic_score: float = 0.0
    llm_agreement_score: float = 0.0


class KnowledgeGraphNodeOut(BaseModel):
    id: Optional[int] = None
    node_key: str
    label: str
    normalized_label: str
    node_type: str
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    confidence: float
    confidence_tier: ConfidenceTierType
    importance_score: float = 0.5
    degree: int = 0
    evidence_count: int = 0
    source_pages: List[int] = Field(default_factory=list)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraphEdgeOut(BaseModel):
    id: Optional[int] = None
    source_key: str
    target_key: str
    relationship: str
    origin: NodeOriginType = "explicit"
    confidence: float
    confidence_tier: ConfidenceTierType
    confidence_breakdown: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    evidence_count: int = 1
    source_pages: List[int] = Field(default_factory=list)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    explanation: Optional[str] = None


class KnowledgeGraphStats(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    hidden_low_confidence_edges: int = 0
    explicit_edges: int = 0
    derived_edges: int = 0
    inferred_edges: int = 0
    high_confidence_edges: int = 0
    medium_confidence_edges: int = 0
    low_confidence_edges: int = 0
    average_edge_confidence: float = 0.0
    grounded_edge_ratio: float = 0.0
    grounded_node_ratio: float = 0.0
    node_type_counts: Dict[str, int] = Field(default_factory=dict)
    relationship_counts: Dict[str, int] = Field(default_factory=dict)
    pages_covered: List[int] = Field(default_factory=list)
    used_research_analysis: bool = False
    is_handwritten: bool = False


class KnowledgeGraphResponse(BaseModel):
    document_id: int
    filename: str
    document_type: str
    is_handwritten: bool
    graph_version: str = GRAPH_VERSION
    content_hash: str
    status: str = "ready"
    generation_method: str = "hybrid"
    cached: bool = False
    is_outdated: bool = False
    include_low_confidence: bool = False
    stats: KnowledgeGraphStats
    nodes: List[KnowledgeGraphNodeOut] = Field(default_factory=list)
    edges: List[KnowledgeGraphEdgeOut] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class KnowledgeGraphDeleteResponse(BaseModel):
    document_id: int
    deleted: bool
    message: str
