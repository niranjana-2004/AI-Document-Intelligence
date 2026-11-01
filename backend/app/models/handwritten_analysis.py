import logging
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
    inspect,
    text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

logger = logging.getLogger(__name__)


class HandwrittenSummary(Base):
    __tablename__ = "handwritten_summaries"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    summary_type = Column(String(30), nullable=False, default="detailed")  # 'quick', 'detailed', 'exam_revision'
    title = Column(String(255), nullable=True)
    overview = Column(Text, nullable=True)
    detailed_content = Column(Text, nullable=True)
    takeaways = Column(JSON, nullable=True)  # list of strings
    key_terms = Column(JSON, nullable=True)  # list of {term, definition, page_number}
    transcription_hash = Column(String(64), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document = relationship("Document", backref="handwritten_summaries")
    user = relationship("User", backref="handwritten_summaries")


class HandwrittenConcept(Base):
    __tablename__ = "handwritten_concepts"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name = Column(String(255), nullable=False, index=True)
    definition = Column(Text, nullable=False)
    excerpt = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=False, default=1)
    related_concepts = Column(JSON, nullable=True)  # list of strings
    is_bookmarked = Column(Boolean, nullable=False, default=False)
    transcription_hash = Column(String(64), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", backref="handwritten_concepts")
    user = relationship("User", backref="handwritten_concepts")


class HandwrittenQuizSet(Base):
    __tablename__ = "handwritten_quiz_sets"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(String(255), nullable=False)
    difficulty = Column(String(20), nullable=False, default="medium")  # 'easy', 'medium', 'hard'
    question_count = Column(Integer, nullable=False, default=5)
    questions = Column(JSON, nullable=False)  # list of question objects
    user_score = Column(Integer, nullable=True)
    user_answers = Column(JSON, nullable=True)  # dict of {question_id: answer}
    transcription_hash = Column(String(64), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document = relationship("Document", backref="handwritten_quizzes")
    user = relationship("User", backref="handwritten_quizzes")


class HandwrittenFlashcardSet(Base):
    __tablename__ = "handwritten_flashcard_sets"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(String(255), nullable=False)
    cards = Column(JSON, nullable=False)  # list of {id, front, back, page_number, known, needs_review}
    transcription_hash = Column(String(64), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document = relationship("Document", backref="handwritten_flashcards")
    user = relationship("User", backref="handwritten_flashcards")


class HandwrittenChatSession(Base):
    __tablename__ = "handwritten_chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", backref="handwritten_chat_sessions")
    user = relationship("User", backref="handwritten_chat_sessions")
    messages = relationship(
        "HandwrittenChatMessage",
        backref="session",
        cascade="all, delete-orphan",
        order_by="HandwrittenChatMessage.created_at.asc()"
    )


class HandwrittenChatMessage(Base):
    __tablename__ = "handwritten_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("handwritten_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role = Column(String(20), nullable=False)  # 'user', 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)  # list of {page_number, excerpt}
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def ensure_handwritten_analysis_schema(engine=None):
    """
    Ensure all handwritten analysis tables exist in SQLite.
    """
    if engine is None:
        from app.core.database import engine as default_engine
        engine = default_engine

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    tables_to_create = [
        ("handwritten_summaries", HandwrittenSummary),
        ("handwritten_concepts", HandwrittenConcept),
        ("handwritten_quiz_sets", HandwrittenQuizSet),
        ("handwritten_flashcard_sets", HandwrittenFlashcardSet),
        ("handwritten_chat_sessions", HandwrittenChatSession),
        ("handwritten_chat_messages", HandwrittenChatMessage),
    ]

    for table_name, model in tables_to_create:
        if table_name not in existing_tables:
            try:
                model.__table__.create(bind=engine, checkfirst=True)
                logger.info(f"Successfully created '{table_name}' table.")
            except Exception as error:
                logger.error(f"Failed to create '{table_name}' table: {error}")

