import re
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.context_service import build_context
from app.services.llm_service import generate_response, generate_suggested_questions_llm, FALLBACK_ANSWER

MIN_CONFIDENCE_THRESHOLD = 0.40

ORDINALS = {
    "first": 1, "1st": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5,
    "sixth": 6, "6th": 6,
}

STOPWORDS = {
    "she", "he", "they", "i", "we", "has", "have", "had", "completed",
    "done", "earned", "holds", "the", "a", "an", "is", "was", "did"
}


def extract_list_items(text: str) -> list[str]:
    """Extract list items from numbered, bulleted, or title lists."""
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Numbered list: 1. Item or 1) Item
        m_num = re.match(r"^(?:\d+[\.\)]|\(\d+\))\s+(.+)$", stripped)
        if m_num:
            item = m_num.group(1).strip()
            item = re.sub(r"\s*\[\d+\]", "", item).strip()
            item = re.sub(r"^\*+|\*+$|^_+|_+$", "", item).strip()
            if item:
                items.append(item)
            continue

        # Bullet list: - Item or * Item or • Item
        m_bullet = re.match(r"^[-*•]\s+(.+)$", stripped)
        if m_bullet:
            item = m_bullet.group(1).strip()
            item = re.sub(r"\s*\[\d+\]", "", item).strip()
            item = re.sub(r"^\*+|\*+$|^_+|_+$", "", item).strip()
            if item:
                items.append(item)
            continue

        # Title: Item
        m_title = re.match(r"^(?:Title|Project)\s*:\s*(.+)$", stripped, re.IGNORECASE)
        if m_title:
            item = m_title.group(1).strip()
            item = re.sub(r"\s*\[\d+\]", "", item).strip()
            if item:
                items.append(item)
            continue

    return items


def extract_topic_from_text(text: str) -> str | None:
    """Extract a topic or entity from a prior user question or assistant text."""
    if not text:
        return None

    cleaned = text.strip()

    # Pattern 1: User question questions like "What is X?", "Tell me about X", etc.
    patterns = [
        r"(?i)^(?:what\s+is|what\s+are|explain|describe|tell\s+me\s+about|details\s+about|information\s+on|who\s+is)\s+(?:the\s+|a\s+|an\s+)?(.+?)(?:\?|\.|$)",
        r"(?i)^(?:did\s+\w+\s+(?:complete|do|have|earn)\s+)(?:the\s+|a\s+|an\s+)?(.+?)(?:\?|\.|$)",
    ]

    for pattern in patterns:
        m = re.match(pattern, cleaned)
        if m:
            topic = m.group(1).strip()
            topic = re.sub(r"[\?\.\!]+$", "", topic).strip()
            if topic and 1 < len(topic) and len(topic.split()) <= 8:
                return topic

    # Pattern 2: Entity like "<Name> certification/project/degree"
    m_ent = re.search(
        r"(?i)\b([A-Za-z0-9\-_]+(?:\s+[A-Za-z0-9\-_]+){0,2}\s+(?:certification|certificate|project|degree|internship|workshop))\b",
        cleaned
    )
    if m_ent:
        words = m_ent.group(1).split()
        while words and words[0].lower() in STOPWORDS:
            words.pop(0)
        if words:
            return " ".join(words)

    # Pattern 3: Quoted topic
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', cleaned)
    if quoted:
        candidate = (quoted[0][0] or quoted[0][1]).strip()
        if candidate and len(candidate.split()) <= 6:
            return candidate

    return None


def resolve_follow_up_query(query: str, history: list | None) -> str:
    """
    Deterministically resolve conversational follow-up references.
    Returns the resolved standalone query, or the original query if unresolvable.
    """
    if not history or not query.strip():
        return query

    query_strip = query.strip()
    query_lower = query_strip.lower()

    # 1. Ordinal/list references (e.g. "the second one", "explain the 2nd one")
    ordinal_match = re.search(
        r"\b(?:the\s+)?(first|second|third|fourth|fifth|sixth|1st|2nd|3rd|4th|5th|6th)\s*(?:one|item|project|topic|certification|point)?\b",
        query_lower
    )
    if ordinal_match:
        ord_word = ordinal_match.group(1)
        target_idx = ORDINALS.get(ord_word)
        if target_idx:
            last_msg = history[-1]
            role = last_msg.get("role", "") if isinstance(last_msg, dict) else getattr(last_msg, "role", "")
            if role == "assistant":
                content = last_msg.get("content", "") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")
                items = extract_list_items(content)
                if items and len(items) >= target_idx:
                    selected_item = items[target_idx - 1]
                    resolved = re.sub(
                        r"(?i)\b(?:the\s+)?(?:first|second|third|fourth|fifth|sixth|1st|2nd|3rd|4th|5th|6th)\s*(?:one|item|project|topic|certification|point)?\b",
                        selected_item,
                        query_strip
                    ).strip()
                    return resolved
            return query

    # 2. Extract recent topic for pronouns / anaphoric phrases
    recent_topic = None
    for msg in reversed(history):
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        topic = extract_topic_from_text(content)
        if topic:
            recent_topic = topic
            break

    if not recent_topic:
        for msg in reversed(history):
            role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "role", "")
            if role == "assistant":
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                m_def = re.match(r"^([A-Z][A-Za-z0-9\s\-_]{2,40})\s+(?:is|refers to|was)\b", content.strip())
                if m_def:
                    recent_topic = m_def.group(1).strip()
                    break

    if recent_topic:
        # Check "its types" / "what are its types"
        if re.search(r"\b(?:what\s+are\s+)?its\s+types\b", query_lower):
            return f"What are the types of {recent_topic}?"

        # Check "when was it completed?" / "when was it done?"
        if re.search(r"\bwhen\s+was\s+it\s+(?:completed|done|finished|awarded|earned|issued)\b", query_lower):
            return f"When was {recent_topic} completed?"

        # Check "explain that further" / "explain it further" / "tell me more about that"
        if re.search(r"\b(?:explain|elaborate\s+on|tell\s+me\s+more\s+about)\s+(?:that|it|this)(?:\s+further)?\b", query_lower):
            return f"Explain {recent_topic} further"

        # General "it" substitution if question is about "it" as subject/object
        if re.search(r"\b(?:what|how|why|where)\s+(?:is|does|was|can)\s+it\b", query_lower):
            return re.sub(r"\bit\b", recent_topic, query_strip, flags=re.IGNORECASE)

    # If reference cannot be resolved reliably, do not invent a topic.
    return query


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
    document_ids: list[int] | None = None,
    top_k: int = 6,
    user_id: int | None = None,
    conversation_history: list | None = None
) -> dict:
    """
    Answer a question using relevant document context and grounded synthesis.
    """
    if not query.strip():
        raise ValueError("Question cannot be empty.")

    # Retrieve history from query metadata if not explicitly provided
    if conversation_history is None:
        conversation_history = getattr(query, "conversation_history", None)

    original_query = str(query)

    # Resolve follow-up query before document retrieval
    retrieval_query = resolve_follow_up_query(original_query, conversation_history)

    context_data = build_context(
        query=retrieval_query,
        db=db,
        document_id=document_id,
        document_ids=document_ids,
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
            "query": original_query,
            "answer": FALLBACK_ANSWER,
            "result_count": 0,
            "results": []
        }

    # --------------------------------------------------
    # Deterministic handling for project list questions
    # --------------------------------------------------
    if (
        (is_project_list_query(original_query) or is_project_list_query(retrieval_query))
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
                query=original_query,
                context=context_data["context"],
                conversation_history=conversation_history
            )
    else:
        answer = generate_response(
            query=original_query,
            context=context_data["context"],
            conversation_history=conversation_history
        )

    return {
        "query": original_query,
        "answer": answer,
        "result_count": context_data["result_count"],
        "results": context_data["results"]
    }


def clean_document_title(filename: str) -> str:
    """Clean filename into human-readable title without extension."""
    if not filename:
        return "Document"
    stem = Path(filename).stem
    cleaned = re.sub(r"[\+_\-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "Document"


def extract_summary_topics(summary_text: str | None) -> list[str]:
    """Extract list or numbered bullet topics from document summary."""
    if not summary_text:
        return []
    topics = []
    for line in summary_text.splitlines():
        line_clean = line.strip()
        m = re.match(r"^(?:\d+[\.\)]|[-*•])\s+(.+)$", line_clean)
        if m:
            topic = m.group(1).strip()
            topic = re.sub(r"[\.\:\;\,\*\_]+$", "", topic).strip()
            topic = re.sub(r"^\*+|\*+$|^_+|_+$", "", topic).strip()
            if 3 < len(topic) <= 90 and not topic.lower().startswith(("here is", "this is", "the following", "overview", "summary")):
                if topic not in topics:
                    topics.append(topic)
    return topics


CATEGORY_QUESTION_TEMPLATES = {
    "technical_skills": "What technical skills and tools are highlighted in {doc_ref}?",
    "projects": "What projects are detailed in {doc_ref}?",
    "certifications": "What certifications or credentials are documented in {doc_ref}?",
    "education": "What is the educational background described in {doc_ref}?",
    "internship": "What internship or practical experience is listed in {doc_ref}?",
    "workshops": "What workshops or training sessions are documented in {doc_ref}?",
    "awards": "What awards or achievements are mentioned in {doc_ref}?",
    "languages": "What languages are documented in {doc_ref}?",
    "career_aspiration": "What career objectives or aspirations are stated in {doc_ref}?",
}


def generate_content_grounded_fallback_questions(
    documents: list[Document],
    db: Session
) -> list[str]:
    """
    Generate content-grounded questions deterministically from document summaries,
    detected chunk categories, and document metadata when LLM is unavailable.
    """
    if not documents:
        return []

    is_multi_doc = len(documents) > 1
    doc_ids = [d.id for d in documents]

    # Query detected chunk categories for all scoped documents
    chunk_rows = (
        db.query(DocumentChunk.document_id, DocumentChunk.category)
        .filter(
            DocumentChunk.document_id.in_(doc_ids),
            DocumentChunk.category.isnot(None)
        )
        .all()
    )

    doc_categories: dict[int, set[str]] = {d.id: set() for d in documents}
    for doc_id, cat in chunk_rows:
        if cat:
            doc_categories[doc_id].add(cat)

    candidate_questions: list[str] = []

    category_priority = [
        "technical_skills",
        "projects",
        "education",
        "certifications",
        "internship",
        "awards",
        "workshops",
        "languages",
        "career_aspiration",
    ]

    for doc in documents:
        cats = doc_categories.get(doc.id, set())
        doc_clean_name = clean_document_title(doc.filename)
        doc_ref = doc_clean_name if is_multi_doc else "this document"

        for cat in category_priority:
            if cat in cats:
                template = CATEGORY_QUESTION_TEMPLATES[cat]
                q = template.format(doc_ref=doc_ref)
                if q not in candidate_questions:
                    candidate_questions.append(q)
                if len(candidate_questions) >= 4:
                    break

        summary_topics = extract_summary_topics(doc.summary)
        for topic in summary_topics:
            if len(candidate_questions) >= 4:
                break
            q = f"What does {doc_ref} explain about {topic}?"
            if q not in candidate_questions:
                candidate_questions.append(q)

        if not cats and not summary_topics and doc.filename:
            q1 = f"What are the main findings and objectives of {doc_clean_name}?"
            q2 = f"Can you summarize the primary topics discussed in {doc_clean_name}?"
            for q in [q1, q2]:
                if q not in candidate_questions:
                    candidate_questions.append(q)

    if is_multi_doc and len(candidate_questions) < 4:
        doc_names = [clean_document_title(d.filename) for d in documents[:2]]
        comp_q = f"What are the key differences or connections between {doc_names[0]} and {doc_names[1]}?"
        if comp_q not in candidate_questions:
            candidate_questions.append(comp_q)

    final_questions = []
    seen = set()
    for q in candidate_questions:
        cleaned = q.strip()
        if not cleaned.endswith("?"):
            cleaned += "?"
        norm = cleaned.lower()
        if norm not in seen:
            seen.add(norm)
            final_questions.append(cleaned)
        if len(final_questions) >= 4:
            break

    return final_questions


def get_document_suggested_questions(
    db: Session,
    user_id: int,
    document_ids: list[int] | None = None
) -> list[str]:
    """
    Retrieve document-aware suggested questions for the given user and document scope.
    Uses local Ollama when available, falling back seamlessly to deterministic content extraction.
    """
    # 1. Enforce ownership and resolve scope
    if document_ids is not None:
        if len(document_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail="Document selection cannot be empty."
            )
        unique_ids = list(dict.fromkeys(document_ids))
        owned_docs = (
            db.query(Document)
            .filter(
                Document.user_id == user_id,
                Document.id.in_(unique_ids)
            )
            .all()
        )
        owned_map = {doc.id: doc for doc in owned_docs}
        if len(owned_map) != len(unique_ids):
            raise HTTPException(
                status_code=404,
                detail="One or more selected documents were not found."
            )
        documents = [owned_map[did] for did in unique_ids]
    else:
        documents = (
            db.query(Document)
            .filter(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .all()
        )

    if not documents:
        return []

    # 2. Filter for usable documents with readable content
    usable_docs = [
        d for d in documents
        if (d.text_length and d.text_length > 0)
        or (d.extracted_text and d.extracted_text.strip())
        or (d.summary and d.summary.strip())
    ]

    if not usable_docs:
        return []

    # 3. Build bounded summary context for Ollama (max ~4 documents, up to 450 chars per doc)
    context_parts = []
    for doc in usable_docs[:4]:
        doc_title = clean_document_title(doc.filename)
        if doc.summary and doc.summary.strip():
            summary_snip = doc.summary.strip()
            if len(summary_snip) > 450:
                summary_snip = summary_snip[:450].rsplit(" ", 1)[0] + "..."
            context_parts.append(f"Document: {doc_title}\nSummary: {summary_snip}")
        elif doc.extracted_text and doc.extracted_text.strip():
            text_snip = doc.extracted_text.strip()[:350]
            context_parts.append(f"Document: {doc_title}\nExcerpt: {text_snip}...")

    summary_context = "\n\n".join(context_parts)

    # 4. Attempt LLM generation using local Ollama
    if summary_context.strip():
        try:
            llm_questions = generate_suggested_questions_llm(summary_context, max_questions=4)
            if len(llm_questions) >= 2:
                return llm_questions[:4]
        except Exception:
            # When Ollama is unreachable, times out, or fails, gracefully proceed to fallback
            pass

    # 5. Fall back to deterministic content-grounded question extraction
    fallback_questions = generate_content_grounded_fallback_questions(usable_docs, db)
    return fallback_questions[:4]
