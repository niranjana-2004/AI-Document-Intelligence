# pyrefly: ignore [missing-import]
from app.services.pdf_service import extract_text_from_pdf
from app.services.text_processing_service import clean_text, chunk_text
from pathlib import Path


def process_document(file_path: Path) -> dict:
    """
    Process an uploaded document.

    Extracts text, cleans it, and splits it into chunks.
    """

    extracted_text = extract_text_from_pdf(file_path)

    cleaned_text = clean_text(extracted_text)

    chunks = chunk_text(
        cleaned_text,
        chunk_size=1000,
        overlap=200
    )

    return {
        "filename": file_path.name,
        "document_type": file_path.suffix.replace(".", "").upper(),
        "text": cleaned_text,
        "text_length": len(cleaned_text),
        "chunks": chunks,
        "chunk_count": len(chunks),
    }