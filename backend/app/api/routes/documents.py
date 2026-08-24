from pathlib import Path

# pyrefly: ignore [missing-import]
from app.services.pdf_service import extract_text_from_pdf
from app.core.database import get_db
from app.models.document import Document

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/")
def get_documents():
    return {
        "message": "Documents endpoint is working!",
        "status": "success"
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

    return {
        "message": "Document uploaded successfully!",
        "document_id": document.id,
        "filename": filename,
        "size": len(file_content),
        "document_type": document.document_type,
        "text_length": len(extracted_text),
        "extracted_text": extracted_text
    }