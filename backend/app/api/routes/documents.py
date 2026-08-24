from pathlib import Path

# pyrefly: ignore [missing-import]
from app.services.pdf_service import extract_text_from_pdf
from app.services.text_processing_service import clean_text, chunk_text
from app.core.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session


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

    extracted_text = ""

    if file_extension == ".pdf":
        extracted_text = extract_text_from_pdf(file_path)

    elif file_extension == ".txt":
        extracted_text = file_content.decode("utf-8", errors="ignore")

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

    cleaned_text = clean_text(extracted_text)

    chunks = chunk_text(
        cleaned_text,
        chunk_size=1000,
        overlap=200
    )

    for index, chunk in enumerate(chunks):
        document_chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=chunk
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