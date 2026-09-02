from app.services.search_service import semantic_search


def build_context(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 7
) -> dict:
    """
    Retrieve relevant document chunks and build
    context for the LLM.

    Only semantically/category-relevant chunks are included.
    Neighboring chunks are not automatically added because
    chunks may contain different document sections.
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
    # Build context using only retrieved relevant chunks
    # --------------------------------------------------

    context_parts = []

    for result in results:

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