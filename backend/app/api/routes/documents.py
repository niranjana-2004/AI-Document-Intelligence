from pathlib import Path
# pyrefly: ignore [missing-import]
from app.services.pdf_service import extract_text_from_pdf
from fastapi import APIRouter, File, UploadFile, HTTPException


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
async def upload_document(file: UploadFile = File(...)):
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

    return {
        "message": "Document uploaded successfully!",
        "filename": filename,
        "size": len(file_content),
        "text_length": len(extracted_text),
        "extracted_text": extracted_text
    }