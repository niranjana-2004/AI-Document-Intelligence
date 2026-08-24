from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from app.api.routes.documents import router as documents_router

app = FastAPI(
    title="AI Document Intelligence API",
    description="Backend API for the AI Document Intelligence platform",
    version="0.1.0"
)

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