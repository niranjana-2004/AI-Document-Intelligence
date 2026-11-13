from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    inspect,
    text,
)
from sqlalchemy.orm import relationship as orm_relationship
from sqlalchemy.sql import func

from app.core.database import Base, engine as default_engine


class CrossDocumentKnowledgeGraph(Base):
    """Persisted source-grounded cross-document knowledge graph snapshot across selected documents."""

    __tablename__ = "cross_document_knowledge_graphs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_hash = Column(String(128), nullable=False, index=True)
    selected_doc_ids_json = Column(JSON, nullable=False, default=list)
    graph_version = Column(String(32), nullable=False, default="cdkg-v1")
    status = Column(String(32), nullable=False, default="ready")
    generation_method = Column(String(64), nullable=False, default="hybrid")
    stats_json = Column(JSON, nullable=False, default=dict)
    diagnostics_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    canonical_entities = orm_relationship(
        "CanonicalEntity",
        back_populates="graph",
        cascade="all, delete-orphan",
    )
    edges = orm_relationship(
        "CrossDocumentEdge",
        back_populates="graph",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_cd_kg_user_hash", "user_id", "collection_hash"),
    )


class CanonicalEntity(Base):
    """Unified canonical entity representing concepts resolved across one or more documents."""

    __tablename__ = "canonical_entities"

    id = Column(Integer, primary_key=True, index=True)
    graph_id = Column(Integer, ForeignKey("cross_document_knowledge_graphs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_key = Column(String(160), nullable=False, index=True)
    canonical_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, default="Concept")
    description = Column(Text, nullable=True)
    aliases_json = Column(JSON, nullable=False, default=list)
    confidence = Column(Float, nullable=False, default=0.85)
    confidence_tier = Column(String(16), nullable=False, default="high")
    importance_score = Column(Float, nullable=False, default=0.5)
    document_count = Column(Integer, nullable=False, default=1)
    occurrence_count = Column(Integer, nullable=False, default=1)
    is_shared = Column(Boolean, nullable=False, default=False)
    documents_json = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=False, default=dict)

    graph = orm_relationship("CrossDocumentKnowledgeGraph", back_populates="canonical_entities")
    occurrences = orm_relationship(
        "EntityOccurrence",
        back_populates="canonical_entity",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_canonical_entities_graph_key", "graph_id", "entity_key"),
        Index("ix_canonical_entities_user_norm", "user_id", "normalized_name"),
    )


class EntityOccurrence(Base):
    """Concrete document-level occurrence linking a canonical entity to specific document evidence."""

    __tablename__ = "entity_occurrences"

    id = Column(Integer, primary_key=True, index=True)
    canonical_entity_id = Column(Integer, ForeignKey("canonical_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    graph_id = Column(Integer, ForeignKey("cross_document_knowledge_graphs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_name = Column(String(255), nullable=False, default="")
    chunk_id = Column(Integer, nullable=True)
    page_number = Column(Integer, nullable=False, default=1)
    original_label = Column(String(255), nullable=False)
    source_text = Column(Text, nullable=False)
    resolution_confidence = Column(Float, nullable=False, default=0.9)
    resolution_method = Column(String(64), nullable=False, default="exact_match")
    evidence_json = Column(JSON, nullable=False, default=dict)

    canonical_entity = orm_relationship("CanonicalEntity", back_populates="occurrences")

    __table_args__ = (
        Index("ix_entity_occurrences_entity_doc", "canonical_entity_id", "document_id"),
        Index("ix_entity_occurrences_graph_doc", "graph_id", "document_id"),
    )


class CrossDocumentEdge(Base):
    """Directed relationship between canonical entities supported by source document evidence."""

    __tablename__ = "cross_document_edges"

    id = Column(Integer, primary_key=True, index=True)
    graph_id = Column(Integer, ForeignKey("cross_document_knowledge_graphs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_entity_id = Column(Integer, ForeignKey("canonical_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(Integer, ForeignKey("canonical_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    source_key = Column(String(160), nullable=False, index=True)
    target_key = Column(String(160), nullable=False, index=True)
    relationship = Column(String(64), nullable=False, index=True)
    origin = Column(String(32), nullable=False, default="explicit")
    confidence = Column(Float, nullable=False, default=0.75)
    confidence_tier = Column(String(16), nullable=False, default="high")
    confidence_breakdown_json = Column(JSON, nullable=False, default=dict)
    evidence_count = Column(Integer, nullable=False, default=1)
    supporting_document_ids_json = Column(JSON, nullable=False, default=list)
    evidence_json = Column(JSON, nullable=False, default=list)
    explanation = Column(Text, nullable=True)
    is_cross_document = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(JSON, nullable=False, default=dict)

    graph = orm_relationship("CrossDocumentKnowledgeGraph", back_populates="edges")

    __table_args__ = (
        Index("ix_cd_edges_graph_rel", "graph_id", "relationship"),
        Index("ix_cd_edges_graph_src_tgt", "graph_id", "source_key", "target_key"),
    )


def ensure_cross_document_knowledge_graph_schema(target_engine=None) -> None:
    """Create and minimally migrate Cross-Document Knowledge Graph tables idempotently."""
    eng = target_engine or default_engine
    Base.metadata.create_all(
        bind=eng,
        tables=[
            CrossDocumentKnowledgeGraph.__table__,
            CanonicalEntity.__table__,
            EntityOccurrence.__table__,
            CrossDocumentEdge.__table__,
        ],
        checkfirst=True,
    )

