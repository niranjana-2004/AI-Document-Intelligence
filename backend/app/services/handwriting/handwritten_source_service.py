import hashlib
import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.services.embedding_services import generate_embedding

logger = logging.getLogger(__name__)


def get_document_transcription_source(
    document_id: int,
    db: Session,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Retrieve canonical transcription text across all pages of a handwritten document.
    Prioritizes edited_transcription over raw_transcription per page.
    Generates a deterministic SHA-256 hash of the content to track versioning.
    """
    query = db.query(Document).filter(Document.id == document_id)
    if user_id is not None:
        query = query.filter(Document.user_id == user_id)
    document = query.first()

    if not document:
        raise ValueError(f"Document #{document_id} not found or access denied.")

    pages = (
        db.query(HandwrittenPage)
        .filter(HandwrittenPage.document_id == document_id)
        .order_by(HandwrittenPage.page_number.asc())
        .all()
    )

    page_items = []
    canonical_sections = []
    transcribed_count = 0

    for page in pages:
        edited = (page.edited_transcription or "").strip()
        raw = (page.raw_transcription or "").strip()

        if edited:
            text = edited
            source_type = "edited"
            transcribed_count += 1
        elif raw:
            text = raw
            source_type = "raw"
            transcribed_count += 1
        else:
            text = ""
            source_type = "none"

        page_items.append({
            "page_id": page.id,
            "page_number": page.page_number,
            "text": text,
            "source_type": source_type,
            "confidence_score": page.confidence_score
        })

        if text:
            canonical_sections.append(f"--- Page {page.page_number} ---\n{text}")

    full_text = "\n\n".join(canonical_sections).strip()

    if full_text:
        content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
    else:
        content_hash = ""

    return {
        "document": document,
        "document_id": document.id,
        "filename": document.filename,
        "total_pages": len(pages),
        "transcribed_pages": transcribed_count,
        "has_transcription": bool(full_text),
        "full_text": full_text,
        "hash": content_hash,
        "pages": page_items
    }


def chunk_text_by_paragraphs(text: str, max_chunk_chars: int = 1200) -> List[str]:
    """
    Split text into logical paragraph chunks without splitting mid-sentence if possible.
    """
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paragraphs:
        # Fallback to newline split
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

    chunks = []
    current = []
    current_len = 0

    for p in paragraphs:
        if current_len + len(p) > max_chunk_chars and current:
            chunks.append("\n\n".join(current))
            current = [p]
            current_len = len(p)
        else:
            current.append(p)
            current_len += len(p) + 2

    if current:
        chunks.append("\n\n".join(current))

    return chunks if chunks else ([text] if text.strip() else [])


def sync_handwritten_chunks_and_embeddings(
    document_id: int,
    db: Session
) -> int:
    """
    Rebuild DocumentChunk records for a handwritten document using its latest transcription.
    Generates 384-dimensional sentence embeddings so semantic and RAG searches operate directly
    on the user's transcribed notes with accurate page citations.
    """
    source_data = get_document_transcription_source(document_id, db)
    document = source_data["document"]
    pages = source_data["pages"]

    # 1. Update Document consolidated text
    document.extracted_text = source_data["full_text"]
    document.text_length = len(source_data["full_text"])

    # 2. Delete existing chunks for this document
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
    db.flush()

    chunk_count = 0
    global_chunk_index = 0

    for page in pages:
        page_text = page["text"].strip()
        if not page_text:
            continue

        page_num = page["page_number"]
        page_chunks = chunk_text_by_paragraphs(page_text, max_chunk_chars=1000)

        for chunk_str in page_chunks:
            if not chunk_str.strip():
                continue

            try:
                emb = generate_embedding(chunk_str)
            except Exception as e:
                logger.warning(f"Failed to generate embedding for page {page_num} chunk: {e}")
                emb = None

            doc_chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=global_chunk_index,
                category="handwritten",
                content=chunk_str,
                embedding=emb,
                page_number=page_num
            )
            db.add(doc_chunk)
            global_chunk_index += 1
            chunk_count += 1

    db.commit()
    logger.info(f"Synchronized {chunk_count} chunks and embeddings for handwritten doc #{document_id}")
    return chunk_count

