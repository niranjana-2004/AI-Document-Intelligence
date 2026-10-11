from pathlib import Path
from docx import Document as DocxDocument
# pyrefly: ignore [missing-import]
from app.services.pdf_service import extract_pages_from_pdf, extract_text_from_pdf
from app.services.text_processing_service import (
    clean_text,
    chunk_text,
    detect_chunk_category
)
from app.services.embedding_services import generate_embedding


class ChunkText(str):
    """
    A string subclass representing chunk text with source page metadata.
    Subclasses str so it remains completely transparent and compatible
    with all existing string consumers and serializations.
    """
    page_number: int | None = None

    def __new__(cls, content: str, page_number: int | None = None):
        instance = super().__new__(cls, content)
        instance.page_number = page_number
        return instance


def process_document(
    file_path: Path,
    file_content: bytes | None = None
) -> dict:
    """
    Process an uploaded document.

    Extracts text, preserves source page numbers for PDFs,
    cleans text, creates chunks, and generates embeddings.
    """

    file_extension = file_path.suffix.lower()

    if file_extension == ".pdf":
        pages = extract_pages_from_pdf(file_path)
        full_text_parts = []
        chunks = []

        for page_info in pages:
            page_num = page_info["page"]
            raw_page_text = page_info["text"]
            cleaned_page_text = clean_text(raw_page_text)

            if cleaned_page_text:
                full_text_parts.append(cleaned_page_text)
                # Chunk page content preserving its verified 1-based page number
                page_chunks = chunk_text(
                    cleaned_page_text,
                    chunk_size=1000,
                    overlap=200
                )
                for chunk_str in page_chunks:
                    chunks.append(ChunkText(chunk_str, page_number=page_num))

        cleaned_text = "\n\n".join(full_text_parts)

    elif file_extension == ".txt":
        if file_content is None:
            file_content = file_path.read_bytes()

        extracted_text = file_content.decode(
            "utf-8",
            errors="ignore"
        )
        cleaned_text = clean_text(extracted_text)
        raw_chunks = chunk_text(
            cleaned_text,
            chunk_size=1000,
            overlap=200
        )
        # Plain text has no pagination; store NULL page number
        chunks = [ChunkText(c, page_number=None) for c in raw_chunks]

    elif file_extension == ".docx":
        docx_file = DocxDocument(str(file_path))

        paragraphs = [
            paragraph.text
            for paragraph in docx_file.paragraphs
            if paragraph.text.strip()
        ]

        extracted_text = "\n".join(paragraphs)
        cleaned_text = clean_text(extracted_text)
        raw_chunks = chunk_text(
            cleaned_text,
            chunk_size=1000,
            overlap=200
        )
        # Word documents have no reliable pagination; store NULL page number
        chunks = [ChunkText(c, page_number=None) for c in raw_chunks]

    else:
        raise ValueError(
            f"Unsupported document type: {file_extension}"
        )

    if not cleaned_text.strip():
        raise ValueError(
            "No readable text was found in the document."
        )

    embeddings = []

    for chunk in chunks:
        embedding = generate_embedding(chunk)
        embeddings.append(embedding)

    return {
        "filename": file_path.name,
        "document_type": file_extension.replace(".", "").upper(),
        "text": cleaned_text,
        "text_length": len(cleaned_text),
        "chunks": chunks,
        "chunk_count": len(chunks),
        "embeddings": embeddings,
        "page_numbers": [getattr(c, "page_number", None) for c in chunks]
    }

