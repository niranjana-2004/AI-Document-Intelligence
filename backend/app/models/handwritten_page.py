import logging
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    Float,
    JSON,
    inspect
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

logger = logging.getLogger(__name__)


class HandwrittenPage(Base):
    __tablename__ = "handwritten_pages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    page_number = Column(
        Integer,
        nullable=False,
        index=True
    )

    original_image_path = Column(
        String(500),
        nullable=False
    )

    processed_image_path = Column(
        String(500),
        nullable=True
    )

    raw_transcription = Column(
        Text,
        nullable=True
    )

    edited_transcription = Column(
        Text,
        nullable=True
    )

    confidence_score = Column(
        Float,
        nullable=True
    )

    has_math = Column(
        Boolean,
        default=False,
        nullable=False
    )

    math_blocks = Column(
        JSON,
        nullable=True
    )

    has_diagrams = Column(
        Boolean,
        default=False,
        nullable=False
    )

    diagram_blocks = Column(
        JSON,
        nullable=True
    )

    status = Column(
        String(30),
        default="pending",
        nullable=False
    )

    error_message = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    document = relationship(
        "Document",
        backref="handwritten_pages"
    )


def ensure_handwritten_pages_schema(engine=None):
    """
    Ensure that the 'handwritten_pages' table exists in the SQLite database.
    """
    if engine is None:
        from app.core.database import engine as default_engine
        engine = default_engine

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "handwritten_pages" not in table_names:
        try:
            HandwrittenPage.__table__.create(bind=engine, checkfirst=True)
            logger.info("Successfully created 'handwritten_pages' table.")
        except Exception as error:
            logger.error(f"Failed to create 'handwritten_pages' table: {error}")


ensure_handwritten_pages_schema()

