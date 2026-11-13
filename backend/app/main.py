from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.models.document import Document
# pyrefly: ignore [missing-import]
from app.api.routes.documents import router as documents_router
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.models.otp import OTPVerification
from app.api.routes.auth import router as auth_router
from app.models.password_reset_token import PasswordResetToken
from app.models.conversation import Conversation, ConversationMessage
from app.api.routes.conversations import router as conversations_router
from app.api.routes.handwritten import router as handwritten_router
from app.api.routes.handwritten_intelligence import router as handwritten_intelligence_router
from app.api.routes.voice import router as voice_router
from app.api.routes.research_paper import router as research_paper_router
from app.api.routes.knowledge_graph import router as knowledge_graph_router
from app.api.routes.cross_document_knowledge_graph import router as cross_document_knowledge_graph_router

app = FastAPI(
    title="AI Document Intelligence API",
    description="Backend API for the AI Document Intelligence platform",
    version="0.1.0"
)

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.services.handwriting.ollama_client import check_ollama_health
from fastapi import Query

Base.metadata.create_all(bind=engine)
from app.models.handwritten_analysis import ensure_handwritten_analysis_schema
from app.models.document_comparison import ensure_document_comparison_schema
from app.models.document_mind_map import ensure_mind_map_schema
from app.models.chat_cache import ensure_chat_cache_schema
from app.models.research_paper_analysis import ensure_research_paper_analysis_schema
from app.models.knowledge_graph import ensure_knowledge_graph_schema
from app.models.cross_document_knowledge_graph import ensure_cross_document_knowledge_graph_schema
ensure_handwritten_analysis_schema(engine)
ensure_document_comparison_schema(engine)
ensure_mind_map_schema(engine)
ensure_chat_cache_schema(engine)
ensure_research_paper_analysis_schema(engine)
ensure_knowledge_graph_schema(engine)
ensure_cross_document_knowledge_graph_schema(engine)

app.include_router(documents_router)
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(handwritten_router)
app.include_router(handwritten_intelligence_router)
app.include_router(voice_router)
app.include_router(research_paper_router)
app.include_router(knowledge_graph_router)
app.include_router(cross_document_knowledge_graph_router)


@app.get("/")
def root():
    return {
        "message": "AI Document Intelligence API is running!",
        "status": "success"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.get("/ai/health")
def ai_health(force_refresh: bool = Query(default=False)):
    """General AI service health check endpoint."""
    return check_ollama_health(force_refresh=force_refresh)
