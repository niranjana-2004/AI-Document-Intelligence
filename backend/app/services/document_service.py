# pyrefly: ignore [missing-import]
from app.services.pdf_service import extract_text_from_pdf
from pathlib import Path

def process_document(file_path: Path) -> dict:
    """
    Process an uploaded document and return extracted information.
    """

    extracted_text = extract_text_from_pdf(file_path)

    return {
        "filename": file_path.name,
        "document_type": file_path.suffix.replace(".", "").upper(),
        "text": extracted_text,
        "text_length": len(extracted_text),
    }