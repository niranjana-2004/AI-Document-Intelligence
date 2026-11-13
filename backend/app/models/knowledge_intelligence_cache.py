from __future__ import annotations

import hashlib
import json
import logging
from typing import List, Optional
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, inspect
from sqlalchemy.sql import func

from app.core.database import Base, engine as default_engine
from app.schemas.knowledge_intelligence import KNOWLEDGE_INTELLIGENCE_VERSION

logger = logging.getLogger(__name__)


class KnowledgeIntelligenceCache(Base):
    """
    Persistent cache for Knowledge Intelligence query responses.
    Strictly tenant-scoped by user_id, document IDs, document content hashes,
    and normalized query text.
    """
    __tablename__ = "knowledge_intelligence_cache"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cache_key = Column(String(64), nullable=False, index=True)
    selected_doc_ids_json = Column(JSON, nullable=False, default=list)
    combined_content_hash = Column(String(64), nullable=False)
    query_text = Column(Text, nullable=False)
    focus_entity = Column(String(160), nullable=True)
    response_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_ki_cache_user_key", "user_id", "cache_key"),
    )


def compute_ki_cache_key(
    user_id: int,
    document_ids: List[int],
    combined_content_hash: str,
    normalized_query: str,
    focus_entity: Optional[str] = None,
    include_low_conf: bool = False,
    skip_llm: bool = False,
) -> str:
    """Compute deterministic SHA-256 cache key for knowledge intelligence queries."""
    sorted_doc_ids = sorted(list(set(document_ids)))
    raw = (
        f"{user_id}:{sorted_doc_ids}:{combined_content_hash}:"
        f"{normalized_query.strip().lower()}:{focus_entity or ''}:"
        f"{include_low_conf}:{skip_llm}:{KNOWLEDGE_INTELLIGENCE_VERSION}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_knowledge_intelligence_schema(target_engine=None) -> None:
    """Ensure the knowledge_intelligence_cache table exists in the database idempotently."""
    eng = target_engine or default_engine
    inspector = inspect(eng)
    if not inspector.has_table("knowledge_intelligence_cache"):
        KnowledgeIntelligenceCache.__table__.create(eng)
        logger.info("Created table knowledge_intelligence_cache")

