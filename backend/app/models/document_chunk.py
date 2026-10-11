from sqlalchemy import Column, Integer, Text, ForeignKey, JSON, String, inspect, text

from app.core.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
        index=True
    )

    chunk_index = Column(
        Integer,
        nullable=False
    )

    category = Column(
        String,
        nullable=True,
        index=True
    )
    content = Column(
        Text,
        nullable=False
    )

    embedding = Column(
        JSON,
        nullable=True
    )

    page_number = Column(
        Integer,
        nullable=True,
        index=True
    )

    def __init__(self, **kwargs):
        if "page_number" not in kwargs or kwargs["page_number"] is None:
            content = kwargs.get("content")
            if hasattr(content, "page_number"):
                kwargs["page_number"] = content.page_number
        super().__init__(**kwargs)


import logging

logger = logging.getLogger(__name__)


def ensure_document_chunks_schema(engine=None):
    """
    Safely and idempotently ensure that the 'page_number' column exists
    in the 'document_chunks' table without dropping or recreating tables.
    """
    if engine is None:
        from app.core.database import engine as default_engine
        engine = default_engine

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "document_chunks" in table_names:
        columns = [c["name"] for c in inspector.get_columns("document_chunks")]
        if "page_number" not in columns:
            try:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE document_chunks ADD COLUMN page_number INTEGER"))
                    conn.commit()
                logger.info("Successfully added 'page_number' column to 'document_chunks' table.")
            except Exception as error:
                logger.error(
                    f"CRITICAL: Failed to add 'page_number' column to 'document_chunks': {error}"
                )
                raise RuntimeError(
                    f"Database schema migration failed for 'document_chunks': {error}"
                ) from error


ensure_document_chunks_schema()