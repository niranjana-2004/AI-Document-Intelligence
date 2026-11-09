import hashlib
import json
import logging
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, inspect, JSON
from sqlalchemy.sql import func
from app.core.database import Base

logger = logging.getLogger(__name__)


class ChatQueryCache(Base):
    """
    Persistent cache for multi-document and single-document chat answers.
    Bound strictly to authenticated user_id, document_ids, and content hashes.
    Any content modification or OCR update invalidates stale cache keys automatically.
    """
    __tablename__ = "chat_query_cache"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cache_key = Column(String(64), nullable=False, index=True)
    document_ids_str = Column(String(255), nullable=False)
    combined_content_hash = Column(String(64), nullable=False)
    query_text = Column(Text, nullable=False)
    response_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_chat_cache_user_key", "user_id", "cache_key"),
    )


def compute_multi_doc_cache_key(
    user_id: int,
    document_ids: list[int] | None,
    combined_hash: str,
    query: str
) -> str:
    """Generate deterministic SHA-256 cache key."""
    doc_ids_sorted = sorted(document_ids) if document_ids else []
    doc_ids_str = ",".join(str(d) for d in doc_ids_sorted)
    raw = f"{user_id}:{doc_ids_str}:{combined_hash}:{query.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_chat_cache_schema(engine):
    """Ensure the chat_query_cache table exists in the database."""
    inspector = inspect(engine)
    if not inspector.has_table("chat_query_cache"):
        ChatQueryCache.__table__.create(engine)
        logger.info("Created 'chat_query_cache' table successfully.")
