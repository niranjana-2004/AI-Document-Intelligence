from pathlib import Path

# pyrefly: ignore [missing-import]
from app.services.document_service import process_document
from app.core.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.search_service import semantic_search
from app.services.question_service import answer_question
from app.schemas.question import QuestionRequest
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import cast
from app.services.llm_service import generate_summary

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/")
def get_documents(db: Session = Depends(get_db)):
    documents = db.query(Document).order_by(
        Document.created_at.desc()
    ).all()

    return {
        "count": len(documents),
        "documents": [
            {
                "id": document.id,
                "filename": document.filename,
                "document_type": document.document_type,
                "text_length": document.text_length,
                "created_at": document.created_at
            }
            for document in documents
        ]
    }

@router.get("/search")
def search_documents(
    query: str,
    document_id: int | None = None,
    top_k: int = 5,
    db: Session = Depends(get_db)
):
    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty."
        )

    if top_k < 1 or top_k > 20:
        raise HTTPException(
            status_code=400,
            detail="top_k must be between 1 and 20."
        )

    results = semantic_search(
        query=query,
        db=db,
        document_id=document_id,
        top_k=top_k
    )

    return {
        "query": query,
        "result_count": len(results),
        "results": results
    }

@router.post("/ask")
def ask_question(
    request: QuestionRequest,
    db: Session = Depends(get_db)
):
    try:
        return answer_question(
            query=request.query,
            db=db,
            document_id=request.document_id,
            top_k=request.top_k
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

@router.get("/{document_id}/summary")
def get_document_summary(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    if not document.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="Document does not contain extracted text."
        )

    try:
        summary = generate_summary(
            cast(str, document.extracted_text)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate document summary: {str(error)}"
        )

    return {
        "document_id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "summary": summary
    }

@router.get("/{document_id}")
def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    return {
        "id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "file_path": document.file_path,
        "text_length": document.text_length,
        "extracted_text": document.extracted_text,
        "created_at": document.created_at
    }

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    allowed_extensions = {".pdf", ".docx", ".txt"}

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is missing."
        )

    filename = Path(file.filename).name
    file_extension = Path(filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX, and TXT files are allowed."
        )

    file_path = UPLOAD_DIR / filename

    file_content = await file.read()

    with open(file_path, "wb") as buffer:
        buffer.write(file_content)

    try:
        processed_document = process_document(
            file_path,
            file_content
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    extracted_text = processed_document["text"]
    chunks = processed_document["chunks"]
    embeddings = processed_document["embeddings"]

    document = Document(
        filename=filename,
        document_type=file_extension.replace(".", "").upper(),
        file_path=str(file_path),
        extracted_text=extracted_text,
        text_length=len(extracted_text)
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    for index, chunk in enumerate(chunks):
        document_chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=chunk,
            embedding=embeddings[index]
        )

        db.add(document_chunk)

    db.commit()

    return {
        "message": "Document uploaded successfully!",
        "document_id": document.id,
        "filename": filename,
        "size": len(file_content),
        "document_type": document.document_type,
        "text_length": len(extracted_text),
        "chunk_count": len(chunks),
        "extracted_text": extracted_text
    }

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    file_path = Path(str(document.file_path))
    if file_path.exists():
        file_path.unlink()

    db.delete(document)
    db.commit()

    return {
        "message": "Document deleted successfully!",
        "document_id": document_id
    }