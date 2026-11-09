from app.services.search_service import semantic_search


def build_context(
    query: str,
    db,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    top_k: int = 6,
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
        document_ids=document_ids,
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
    is_multi = (document_ids is not None and len(document_ids) > 1)

    for idx, result in enumerate(results, start=1):
        result["citation_index"] = idx

        doc_title = result.get("document_title") or result.get("filename") or "Unknown Document"
        source_type = (result.get("source_type") or "printed").title()
        chunk_id = result.get("chunk_id", "N/A")
        page_val = result.get("page") or result.get("page_number")
        page_str = str(page_val) if page_val is not None else "N/A"
        content = (result.get("content") or "").strip()

        if is_multi:
            context_parts.append(
                f"[Source {idx} | Document: {doc_title} | Type: {source_type} | Page: {page_str} | Chunk: {chunk_id}]\n"
                f"{content}"
            )
        else:
            filename = result.get("filename") or "Unknown Document"
            context_parts.append(
                f"[Source {idx} | Document: {filename} | Page: {page_str}]\n"
                f"{content}"
            )

    context = "\n\n".join(context_parts)

    return {
        "query": query,
        "context": context,
        "results": results,
        "result_count": len(results),
        "is_multi_document": is_multi
    }