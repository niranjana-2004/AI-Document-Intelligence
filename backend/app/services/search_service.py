from app.services.embedding_services import generate_embedding
from app.services.similarity_service import cosine_similarity
from app.models.document_chunk import DocumentChunk


def semantic_search(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 5
):
    query_embedding = generate_embedding(query)

    query = db.query(DocumentChunk)

    if document_id is not None:
        query = query.filter(
            DocumentChunk.document_id == document_id
        )

    chunks = query.all()

    results = []

    for chunk in chunks:

        if not chunk.embedding:
            continue

        similarity = cosine_similarity(
            query_embedding,
            chunk.embedding
        )

        results.append({
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "similarity": similarity
        })

    results.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    return results[:top_k]