from fastapi import FastAPI
from app.core.database import Base, engine
from app.models.document import Document
# pyrefly: ignore [missing-import]
from app.api.routes.documents import router as documents_router
from app.models.document_chunk import DocumentChunk

app = FastAPI(
    title="AI Document Intelligence API",
    description="Backend API for the AI Document Intelligence platform",
    version="0.1.0"
)
Base.metadata.create_all(bind=engine)
app.include_router(documents_router)

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