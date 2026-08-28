from app.services.search_service import semantic_search
from app.models.document_chunk import DocumentChunk


def build_context(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 7
) -> dict:
    """
    Retrieve relevant document chunks and build
    context for the LLM.

    Neighboring chunks are included to prevent important
    information from being lost when a section is split
    across multiple chunks.
    """

    results = semantic_search(
        query=query,
        db=db,
        document_id=document_id,
        top_k=top_k
    )

    if not results:
        return {
            "query": query,
            "context": "",
            "results": [],
            "result_count": 0
        }

    # --------------------------------------------------
    # Collect relevant chunk IDs and neighboring chunks
    # --------------------------------------------------

    selected_chunks = {}

    for result in results:

        selected_chunks[result["chunk_id"]] = result

        chunk_index = result["chunk_index"]
        current_document_id = result["document_id"]

        # Get previous chunk
        previous_chunk = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == current_document_id,
                DocumentChunk.chunk_index == chunk_index - 1
            )
            .first()
        )

        if previous_chunk:
            selected_chunks[previous_chunk.id] = {
                "chunk_id": previous_chunk.id,
                "document_id": previous_chunk.document_id,
                "chunk_index": previous_chunk.chunk_index,
                "content": previous_chunk.content,
                "similarity": 0.0,
                "keyword_score": 0.0,
                "category": result.get("category"),
                "category_boost": 0.0,
                "final_score": 0.0
            }

        # Get next chunk
        next_chunk = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == current_document_id,
                DocumentChunk.chunk_index == chunk_index + 1
            )
            .first()
        )

        if next_chunk:
            selected_chunks[next_chunk.id] = {
                "chunk_id": next_chunk.id,
                "document_id": next_chunk.document_id,
                "chunk_index": next_chunk.chunk_index,
                "content": next_chunk.content,
                "similarity": 0.0,
                "keyword_score": 0.0,
                "category": result.get("category"),
                "category_boost": 0.0,
                "final_score": 0.0
            }

    # --------------------------------------------------
    # Sort chunks in their original document order
    # --------------------------------------------------

    ordered_chunks = sorted(
        selected_chunks.values(),
        key=lambda x: (
            x["document_id"],
            x["chunk_index"]
        )
    )

    # --------------------------------------------------
    # Build LLM context
    # --------------------------------------------------

    context_parts = []

    for result in ordered_chunks:

        context_parts.append(
            f"[Document Chunk {result['chunk_index']}]\n"
            f"{result['content']}"
        )

    context = "\n\n".join(context_parts)

    return {
        "query": query,
        "context": context,
        "results": results,
        "result_count": len(results)
    }