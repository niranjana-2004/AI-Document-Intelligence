from sqlalchemy.orm import query
from app.services.context_service import build_context
from app.services.llm_service import generate_response
import re

def extract_project_titles(results: list[dict]) -> list[str]:
    """
    Extract project titles directly from retrieved project chunks.
    """

    titles = []

    for result in results:
        if result.get("query_intent") != "projects":
            continue

        content = result.get("content", "")

        matches = re.findall(
            r"(?im)^\s*Title\s*:\s*(.+?)\s*(?:\([^)]*\))?\s*$",
            content
        )

        for title in matches:
            title = title.strip()

            if title and title not in titles:
                titles.append(title)

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
            answer = "\n".join(
                project_titles
            )
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