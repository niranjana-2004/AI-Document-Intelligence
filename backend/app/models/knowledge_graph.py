from __future__ import annotations

from sqlalchemy import (
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


class KnowledgeGraph(Base):
    """Persisted source-grounded knowledge graph snapshot for a document."""

    __tablename__ = "knowledge_graphs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    content_hash = Column(String(128), nullable=False, index=True)
    graph_version = Column(String(32), nullable=False, default="kg-v1")
    status = Column(String(32), nullable=False, default="ready")
    generation_method = Column(String(64), nullable=False, default="hybrid")
    stats_json = Column(JSON, nullable=False, default=dict)
    diagnostics_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    nodes = orm_relationship(
        "KnowledgeGraphNode",
        back_populates="graph",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    edges = orm_relationship(
        "KnowledgeGraphEdge",
        back_populates="graph",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_knowledge_graphs_user_doc", "user_id", "document_id"),
    )


class KnowledgeGraphNode(Base):
    """Typed entity or concept node grounded in concrete document evidence."""

    __tablename__ = "knowledge_graph_nodes"

    id = Column(Integer, primary_key=True, index=True)
    graph_id = Column(Integer, ForeignKey("knowledge_graphs.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    node_key = Column(String(160), nullable=False, index=True)
    label = Column(String(255), nullable=False)
    normalized_label = Column(String(255), nullable=False, index=True)
    node_type = Column(String(64), nullable=False, default="Concept")
    description = Column(Text, nullable=True)
    aliases_json = Column(JSON, nullable=False, default=list)
    confidence = Column(Float, nullable=False, default=0.75)
    confidence_tier = Column(String(16), nullable=False, default="high")
    importance_score = Column(Float, nullable=False, default=0.5)
    evidence_count = Column(Integer, nullable=False, default=0)
    source_pages_json = Column(JSON, nullable=False, default=list)
    evidence_json = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=False, default=dict)

    graph = orm_relationship("KnowledgeGraph", back_populates="nodes")

    __table_args__ = (
        Index("ix_kg_nodes_graph_key", "graph_id", "node_key"),
    )


class KnowledgeGraphEdge(Base):
    """Directed typed relationship edge grounded in concrete document evidence."""

    __tablename__ = "knowledge_graph_edges"

    id = Column(Integer, primary_key=True, index=True)
    graph_id = Column(Integer, ForeignKey("knowledge_graphs.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id = Column(Integer, ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id = Column(Integer, ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    source_key = Column(String(160), nullable=False, index=True)
    target_key = Column(String(160), nullable=False, index=True)
    relationship = Column(String(64), nullable=False, index=True)
    origin = Column(String(32), nullable=False, default="explicit")
    confidence = Column(Float, nullable=False, default=0.75)
    confidence_tier = Column(String(16), nullable=False, default="high")
    confidence_breakdown_json = Column(JSON, nullable=False, default=dict)
    evidence_count = Column(Integer, nullable=False, default=1)
    source_pages_json = Column(JSON, nullable=False, default=list)
    evidence_json = Column(JSON, nullable=False, default=list)
    explanation = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)

    graph = orm_relationship("KnowledgeGraph", back_populates="edges")

    __table_args__ = (
        Index("ix_kg_edges_graph_rel", "graph_id", "relationship"),
    )


def ensure_knowledge_graph_schema(target_engine=None) -> None:
    """Create and minimally migrate Knowledge Graph tables idempotently."""
    eng = target_engine or default_engine
    Base.metadata.create_all(
        bind=eng,
        tables=[
            KnowledgeGraph.__table__,
            KnowledgeGraphNode.__table__,
            KnowledgeGraphEdge.__table__,
        ],
        checkfirst=True,
    )

    inspector = inspect(eng)
    kg_cols = {col["name"] for col in inspector.get_columns("knowledge_graphs")}
    alter_statements = []
    if "diagnostics_json" not in kg_cols:
        alter_statements.append("ALTER TABLE knowledge_graphs ADD COLUMN diagnostics_json JSON NOT NULL DEFAULT '{}'")
    if "graph_version" not in kg_cols:
        alter_statements.append("ALTER TABLE knowledge_graphs ADD COLUMN graph_version VARCHAR(32) NOT NULL DEFAULT 'kg-v1'")

    if alter_statements:
        with eng.begin() as conn:
            for stmt in alter_statements:
                conn.execute(text(stmt))
