from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "documents.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Import models so SQLAlchemy knows about all tables
try:
    from app.models.user import User
    from app.models.otp import OTPVerification
    from app.models.password_reset_token import PasswordResetToken
    from app.models.activity import ActivityLog
    from app.models.conversation import Conversation, ConversationMessage
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.handwritten_page import HandwrittenPage
    from app.models.handwritten_analysis import (
        HandwrittenSummary,
        HandwrittenConcept,
        HandwrittenQuizSet,
        HandwrittenFlashcardSet,
        HandwrittenChatSession,
        HandwrittenChatMessage,
        ensure_handwritten_analysis_schema
    )
    ensure_handwritten_analysis_schema(engine)
except ImportError:
    # Avoid circular import when a model imports Base from database
    pass
