from fastapi import FastAPI
from app.core.database import Base, engine
from fastapi.middleware.cors import CORSMiddleware
from app.models.document import Document
# pyrefly: ignore [missing-import]
from app.api.routes.documents import router as documents_router
from app.models.document_chunk import DocumentChunk

app = FastAPI(
    title="AI Document Intelligence API",
    description="Backend API for the AI Document Intelligence platform",
    version="0.1.0"
)

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