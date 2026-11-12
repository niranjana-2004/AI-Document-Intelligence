import logging
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    inspect,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

logger = logging.getLogger(__name__)


class ResearchPaperAnalysis(Base):
    """
    Persistent cache for structured source-grounded research paper analyses.
    Keyed by user ownership, document ID, and SHA-256 content_hash so any edit,
    re-OCR, chunk update, or manual classification override invalidates stale results.
    """

    __tablename__ = "research_paper_analyses"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_hash = Column(String(64), nullable=False, index=True)
    analysis_version = Column(String(32), nullable=False, default="phase1_v1")
    classification_override = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False, default="completed")
    analysis_mode = Column(String(32), nullable=False, default="deterministic_fallback")

    paper_detection = Column(JSON, nullable=False)
    basic_information = Column(JSON, nullable=False)
    research_context = Column(JSON, nullable=False)
    methodology = Column(JSON, nullable=False)
    evaluation = Column(JSON, nullable=False)
    conclusion = Column(JSON, nullable=False)
    sections = Column(JSON, nullable=False)
    numerical_data = Column(JSON, nullable=False)
    tables_and_figures = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    timings = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document = relationship("Document", backref="research_analyses")
    user = relationship("User", backref="research_analyses")


def ensure_research_paper_analysis_schema(engine=None):
    """
    Safely and idempotently ensure the 'research_paper_analyses' table exists.
    """
    if engine is None:
        from app.core.database import engine as default_engine
        engine = default_engine

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "research_paper_analyses" not in table_names:
        try:
            ResearchPaperAnalysis.__table__.create(engine, checkfirst=True)
            logger.info("Created 'research_paper_analyses' table successfully.")
        except Exception as exc:
            logger.warning("Could not auto-create 'research_paper_analyses' table: %s", exc)

