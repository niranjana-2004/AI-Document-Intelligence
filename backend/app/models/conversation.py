import logging
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, inspect
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

logger = logging.getLogger(__name__)


class Conversation(Base):
    __tablename__ = "conversations"

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

    title = Column(
        String(255),
        nullable=False,
        default="New Conversation"
    )

    scope_mode = Column(
        String(20),
        nullable=False,
        default="all"
    )

    selected_doc_ids = Column(
        JSON,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True
    )

    # Cascade delete messages when a conversation is deleted
    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at"
    )

    user = relationship("User")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    role = Column(
        String(20),
        nullable=False
    )

    content = Column(
        Text,
        nullable=False
    )

    sources = Column(
        JSON,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )

    conversation = relationship("Conversation", back_populates="messages")


def ensure_conversations_schema(engine=None):
    """
    Safely and idempotently ensure that the 'conversations' and 'conversation_messages'
    tables exist in the database without dropping or altering existing tables.
    """
    if engine is None:
        from app.core.database import engine as default_engine
        engine = default_engine

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    tables_to_create = []
    if "conversations" not in existing_tables:
        tables_to_create.append(Conversation.__table__)
    if "conversation_messages" not in existing_tables:
        tables_to_create.append(ConversationMessage.__table__)

    if tables_to_create:
        try:
            Base.metadata.create_all(bind=engine, tables=tables_to_create)
            logger.info("Successfully initialized conversations database tables.")
        except Exception as error:
            logger.error(f"CRITICAL: Failed to initialize conversation tables: {error}")
            raise RuntimeError(f"Database schema initialization failed for conversations: {error}") from error


ensure_conversations_schema()
