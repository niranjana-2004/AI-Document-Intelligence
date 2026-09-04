from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.text_processing_service import (
    chunk_text,
    detect_chunk_category
)
from app.services.embedding_services import generate_embedding


DOCUMENT_ID = 1


db = SessionLocal()

try:

    document = (
        db.query(Document)
        .filter(Document.id == DOCUMENT_ID)
        .first()
    )

    if not document:
        print(f"Document {DOCUMENT_ID} not found.")
        raise SystemExit(1)

    print(f"Re-indexing: {document.filename}")

    # Create new section-aware chunks
    chunks = chunk_text(
        document.extracted_text,
        chunk_size=1000,
        overlap=200
    )

    print(f"New chunk count: {len(chunks)}")

    # Delete old chunks
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == DOCUMENT_ID
    ).delete(synchronize_session=False)

    db.commit()

    print("Old chunks deleted.")

    # Create new chunks and embeddings
    for index, chunk in enumerate(chunks):

        category = detect_chunk_category(chunk)

        print(
            f"Creating chunk {index}: "
            f"category={category}"
        )

        embedding = generate_embedding(chunk)

        document_chunk = DocumentChunk(
            document_id=DOCUMENT_ID,
            chunk_index=index,
            category=category,
            content=chunk,
            embedding=embedding
        )

        db.add(document_chunk)

    db.commit()

    print()
    print("Re-indexing completed successfully!")

except Exception as error:

    db.rollback()

    print()
    print("ERROR:")
    print(error)

    raise

finally:

    db.close()