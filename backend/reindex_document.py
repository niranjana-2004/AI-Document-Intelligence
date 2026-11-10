from pathlib import Path
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.document_service import ChunkText, process_document
from app.services.text_processing_service import (
    chunk_text,
    detect_chunk_category
)
from app.services.embedding_services import generate_embedding


def reindex_document_chunks(document_id: int, db=None) -> int:
    """Re-index a document while preserving PDF page_number metadata whenever source file exists."""
    own_db = db is None
    if own_db:
        db = SessionLocal()

    try:
        document = (
            db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )
        if not document:
            raise ValueError(f"Document {document_id} not found.")

        file_path = Path(str(document.file_path)) if document.file_path else None
        if not file_path or not file_path.exists():
            backend_root = Path(__file__).resolve().parent
            if document.file_path:
                alt = backend_root / str(document.file_path)
                if alt.exists():
                    file_path = alt

        if file_path and file_path.exists() and (document.document_type or "").upper() in {"PDF", "DOCX", "TXT"}:
            processed = process_document(file_path)
            chunks = processed["chunks"]
            embeddings = processed["embeddings"]
            page_numbers = processed.get("page_numbers", [])
        else:
            raw_chunks = chunk_text(document.extracted_text or "", chunk_size=1000, overlap=200)
            chunks = [ChunkText(c, page_number=None) for c in raw_chunks]
            embeddings = [generate_embedding(c) for c in chunks]
            page_numbers = [None] * len(chunks)

        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).delete(synchronize_session=False)
        db.commit()

        for index, chunk in enumerate(chunks):
            category = detect_chunk_category(chunk)
            page_num = getattr(chunk, "page_number", None)
            if page_num is None and index < len(page_numbers):
                page_num = page_numbers[index]

            document_chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                category=category,
                content=str(chunk),
                embedding=embeddings[index],
                page_number=page_num,
            )
            db.add(document_chunk)

        db.commit()
        return len(chunks)
    except Exception:
        db.rollback()
        raise
    finally:
        if own_db:
            db.close()


if __name__ == "__main__":
    import sys
    doc_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    count = reindex_document_chunks(doc_id)
    print(f"Re-indexed document #{doc_id} cleanly with {count} chunks.")