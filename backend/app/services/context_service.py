from app.services.search_service import semantic_search


def build_context(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 7,
    user_id: int | None = None
) -> dict:
    """
    Retrieve relevant document chunks and build structured context
    for grounded answer synthesis with traceable source citations.

    Each retrieved chunk is assigned a stable 1-based citation index
    corresponding directly to [Source N] in the LLM prompt context.
    """

    results = semantic_search(
        query=query,
        db=db,
        document_id=document_id,
        top_k=top_k,
        user_id=user_id
    )

    if not results:
        return {
            "query": query,
            "context": "",
            "results": [],
            "result_count": 0
        }

    # --------------------------------------------------
    # Assign stable citation numbers and build LLM context
    # --------------------------------------------------

    context_parts = []

    for idx, result in enumerate(results, start=1):
        result["citation_index"] = idx

        filename = result.get("filename") or "Unknown Document"
        page_number = result.get("page_number")
        page_str = str(page_number) if page_number is not None else "N/A"
        content = (result.get("content") or "").strip()

        context_parts.append(
            f"[Source {idx} | Document: {filename} | Page: {page_str}]\n"
            f"{content}"
        )

    context = "\n\n".join(context_parts)

    return {
        "query": query,
        "context": context,
        "results": results,
        "result_count": len(results)
    }