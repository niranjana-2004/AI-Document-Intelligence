import logging
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    JSON,
    inspect
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

logger = logging.getLogger(__name__)


class DocumentMindMap(Base):
    """
    Persistent cache for generated document mind maps.
    Tracks user ownership and content SHA-256 hash to automatically invalidate
    stale mind maps when document content changes.
    """
    __tablename__ = "document_mind_maps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    content_hash = Column(String(64), nullable=False, index=True)
    mind_map_json = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document = relationship("Document", backref="mind_maps")
    user = relationship("User", backref="mind_maps")


def ensure_mind_map_schema(engine=None):
    """
    Safely and idempotently ensure that the 'document_mind_maps' table exists in SQLite.
    """
    if engine is None:
        from app.core.database import engine as default_engine
        engine = default_engine

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "document_mind_maps" not in table_names:
        try:
            DocumentMindMap.__table__.create(engine, checkfirst=True)
            logger.info("Created 'document_mind_maps' table successfully.")
        except Exception as e:
            logger.warning(f"Could not auto-create 'document_mind_maps' table: {e}")

