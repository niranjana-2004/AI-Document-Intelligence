import logging
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    JSON,
    inspect,
    text
)
from sqlalchemy.sql import func

from app.core.database import Base

logger = logging.getLogger(__name__)


class DocumentComparison(Base):
    """
    Cached and persisted semantic comparison record between two documents.
    Tracks SHA-256 content hashes of Document A and Document B to ensure
    automatic cache invalidation if either document is edited or updated.
    """
    __tablename__ = "document_comparisons"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    document_a_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    document_b_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    document_a_hash = Column(
        String(64),
        nullable=False
    )

    document_b_hash = Column(
        String(64),
        nullable=False
    )

    comparison_result = Column(
        JSON,
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


def ensure_document_comparison_schema(engine=None):
    """
    Safely and idempotently ensure that the 'document_comparisons' table exists in the database.
    """
    if engine is None:
        from app.core.database import engine as default_engine
        engine = default_engine

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "document_comparisons" not in table_names:
        try:
            DocumentComparison.__table__.create(bind=engine, checkfirst=True)
            logger.info("Created 'document_comparisons' table in database.")
        except Exception as error:
            logger.error(f"Error creating 'document_comparisons' table: {error}")

