from pathlib import Path

# pyrefly: ignore [missing-import]
from app.services.pdf_service import extract_text_from_pdf
from app.services.text_processing_service import clean_text, chunk_text
from app.services.embedding_services import generate_embedding


def process_document(
    file_path: Path,
    file_content: bytes | None = None
) -> dict:
    """
    Process an uploaded document.

    Extracts text, cleans it, creates chunks,
    and generates embeddings.
    """

    file_extension = file_path.suffix.lower()

    if file_extension == ".pdf":
        extracted_text = extract_text_from_pdf(file_path)

    elif file_extension == ".txt":
        if file_content is None:
            file_content = file_path.read_bytes()

        extracted_text = file_content.decode(
            "utf-8",
            errors="ignore"
        )

    else:
        raise ValueError(
            f"Unsupported document type: {file_extension}"
        )

    cleaned_text = clean_text(extracted_text)

    chunks = chunk_text(
        cleaned_text,
        chunk_size=1000,
        overlap=200
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
        "embeddings": embeddings
    }