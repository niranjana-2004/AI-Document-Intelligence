from app.services.context_service import build_context
from app.services.llm_service import generate_response


def answer_question(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 7
) -> dict:
    """
    Answer a question using relevant document context.
    """

    if not query.strip():
        raise ValueError("Question cannot be empty.")

    context_data = build_context(
        query=query,
        db=db,
        document_id=document_id,
        top_k=top_k
    )

    if context_data["result_count"] == 0:
        return {
            "query": query,
            "answer": "I couldn't find relevant information in the provided documents.",
            "result_count": 0,
            "results": []
        }

    print("\n========== CONTEXT SENT TO LLM ==========")
    print(context_data["context"])
    print("==========================================\n")

    answer = generate_response(
        query=query,
        context=context_data["context"]
    )

    return {
        "query": query,
        "answer": answer,
        "result_count": context_data["result_count"],
        "results": context_data["results"]
    }