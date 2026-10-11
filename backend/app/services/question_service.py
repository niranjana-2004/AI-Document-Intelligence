import re
from app.services.context_service import build_context
from app.services.llm_service import generate_response, FALLBACK_ANSWER

MIN_CONFIDENCE_THRESHOLD = 0.40


def extract_project_titles(results: list[dict]) -> list[str]:
    """
    Extract project titles directly from retrieved project chunks,
    attaching grounded inline citations matching the chunk's citation index.
    """
    titles = []

    for result in results:
        if result.get("query_intent") != "projects":
            continue

        citation_idx = result.get("citation_index")
        cite_str = f" [{citation_idx}]" if citation_idx else ""
        content = result.get("content", "")

        matches = re.findall(
            r"(?im)^\s*Title\s*:\s*(.+?)\s*(?:\([^)]*\))?\s*$",
            content
        )

        for title in matches:
            title = title.strip()
            if title:
                entry = f"{title}{cite_str}"
                if entry not in titles:
                    titles.append(entry)

    return titles


def is_project_list_query(query: str) -> bool:
    """
    Determine whether the user is asking for a list of projects.
    """
    query_lower = query.lower().strip()

    project_list_phrases = [
        "what projects",
        "which projects",
        "list projects",
        "list of projects",
        "projects has",
        "projects have",
        "projects did",
        "what are the projects",
        "what are niranjana's projects",
        "what are her projects",
    ]

    return any(
        phrase in query_lower
        for phrase in project_list_phrases
    )


def answer_question(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 6,
    user_id: int | None = None
) -> dict:
    """
    Answer a question using relevant document context and grounded synthesis.
    """
    if not query.strip():
        raise ValueError("Question cannot be empty.")

    context_data = build_context(
        query=query,
        db=db,
        document_id=document_id,
        top_k=top_k,
        user_id=user_id
    )

    # --------------------------------------------------
    # Minimum confidence gate
    # --------------------------------------------------
    # If no results returned or if the highest-ranking chunk score is below
    # the minimum confidence threshold, return fallback answer without calling Ollama.
    top_chunk_score = (
        context_data["results"][0].get("final_score", 0.0)
        if context_data["results"]
        else 0.0
    )

    if (
        context_data["result_count"] == 0
        or top_chunk_score < MIN_CONFIDENCE_THRESHOLD
    ):
        return {
            "query": query,
            "answer": FALLBACK_ANSWER,
            "result_count": 0,
            "results": []
        }

    # --------------------------------------------------
    # Deterministic handling for project list questions
    # --------------------------------------------------
    if (
        is_project_list_query(query)
        and any(
            result.get("query_intent") == "projects"
            for result in context_data["results"]
        )
    ):
        project_titles = extract_project_titles(
            context_data["results"]
        )

        if project_titles:
            answer = "\n".join(project_titles)
        else:
            answer = generate_response(
                query=query,
                context=context_data["context"]
            )
    else:
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