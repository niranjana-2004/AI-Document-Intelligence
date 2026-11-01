import logging
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    inspect,
    text
)
from sqlalchemy.sql import func

from app.core.database import Base

logger = logging.getLogger(__name__)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )
    filename = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=True)
    text_length = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    is_handwritten = Column(Boolean, default=False, nullable=True)
    processing_status = Column(String(50), default="completed", nullable=True)
    processing_progress = Column(Integer, default=100, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def ensure_documents_schema(engine=None):
    """
    Safely and idempotently ensure that the 'is_handwritten', 'processing_status',
    and 'processing_progress' columns exist in the 'documents' table.
    """
    if engine is None:
        from app.core.database import engine as default_engine
        engine = default_engine

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "documents" in table_names:
        columns = [c["name"] for c in inspector.get_columns("documents")]
        try:
            with engine.connect() as conn:
                if "is_handwritten" not in columns:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN is_handwritten BOOLEAN DEFAULT 0"))
                if "processing_status" not in columns:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN processing_status VARCHAR(50) DEFAULT 'completed'"))
                if "processing_progress" not in columns:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN processing_progress INTEGER DEFAULT 100"))
                conn.commit()
            logger.info("Successfully ensured documents table schema extensions.")
        except Exception as error:
            logger.error(f"Schema migration warning for 'documents': {error}")


ensure_documents_schema()
