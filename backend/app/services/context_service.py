from app.services.search_service import semantic_search


def build_context(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 5
) -> dict:
    """
    Retrieve relevant document chunks and build
    context for the LLM.
    """

    results = semantic_search(
        query=query,
        db=db,
        document_id=document_id,
        top_k=top_k
    )

    context_parts: list[str] = []

    for result in results:
        context_parts.append(
            str(result["content"])
        )

    context = "\n\n".join(context_parts)

    return {
        "query": query,
        "context": context,
        "results": results,
        "result_count": len(results)
    }