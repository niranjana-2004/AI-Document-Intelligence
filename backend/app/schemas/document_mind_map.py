from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SourceEvidence(BaseModel):
    """Verifiable source citation for a node."""
    page: int = Field(default=1, description="Source page number where evidence appears")
    chunk_id: Optional[str] = Field(default=None, description="Optional chunk identifier")
    excerpt: str = Field(description="Exact or near-exact quote from document text")
    confidence: float = Field(default=0.90, description="Evidence confidence score")


class MindMapNode(BaseModel):
    """A structured node in the mind map hierarchy."""
    id: str = Field(description="Unique node identifier, e.g. root, topic-1, concept-1-2")
    label: str = Field(description="Concept or topic display label")
    type: str = Field(
        default="concept",
        description="Node type: root, topic, subtopic, concept, definition, process, example"
    )
    description: Optional[str] = Field(default=None, description="Concise explanation or definition")
    relationship: Optional[str] = Field(
        default=None,
        description="Relationship to parent: contains, depends_on, causes, related_to, example_of, part_of, leads_to"
    )
    children: List[MindMapNode] = Field(default_factory=list, description="Child nodes in hierarchy")
    sources: List[SourceEvidence] = Field(default_factory=list, description="Supporting document citations")


# For recursive Pydantic v2 resolution
MindMapNode.model_rebuild()


class MindMapRequest(BaseModel):
    """Optional payload for mind-map generation."""
    force_refresh: bool = Field(default=False, description="Whether to bypass cached map and force re-generation")


class MindMapResponse(BaseModel):
    """Complete structured mind-map representation returned to the frontend."""
    document_id: int
    document_title: str
    is_handwritten: bool
    content_hash: str
    node_count: int
    root: MindMapNode
    cached: bool = False
    generation_method: str = "ollama_llama3_2"

