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
    HandwrittenChatMessage
)
from app.models.document_comparison import DocumentComparison, ensure_document_comparison_schema
from app.models.document_mind_map import DocumentMindMap, ensure_mind_map_schema
from app.models.chat_cache import ChatQueryCache, ensure_chat_cache_schema

__all__ = [
    "User",
    "OTPVerification",
    "PasswordResetToken",
    "ActivityLog",
    "Conversation",
    "ConversationMessage",
    "Document",
    "DocumentChunk",
    "HandwrittenPage",
    "HandwrittenSummary",
    "HandwrittenConcept",
    "HandwrittenQuizSet",
    "HandwrittenFlashcardSet",
    "HandwrittenChatSession",
    "HandwrittenChatMessage",
    "DocumentComparison",
    "ensure_document_comparison_schema",
    "DocumentMindMap",
    "ensure_mind_map_schema",
    "ChatQueryCache",
    "ensure_chat_cache_schema"
]

