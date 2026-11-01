import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.handwritten_analysis import HandwrittenConcept
from app.services.handwriting.handwritten_source_service import get_document_transcription_source
from app.services.handwriting.ollama_client import query_ollama_json, OllamaError

logger = logging.getLogger(__name__)


def generate_handwritten_concepts(
    document_id: int,
    user_id: int,
    db: Session
) -> List[Dict[str, Any]]:
    """
    Extract structured academic concepts, definitions, supporting excerpts,
    and page numbers from handwritten notes.
    """
    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    if not source_data["has_transcription"]:
        raise ValueError("Cannot extract concepts: this document has no transcription yet.")

    full_notes = source_data["full_text"]
    current_hash = source_data["hash"]

    # Keep track of which concepts were previously bookmarked by user so we don't lose bookmarks on regeneration
    existing_records = (
        db.query(HandwrittenConcept)
        .filter(HandwrittenConcept.document_id == document_id)
        .all()
    )
    bookmarked_names = {c.name.strip().lower() for c in existing_records if c.is_bookmarked}

    system_prompt = (
        "You are an academic concept extraction engine. "
        "Your task is to identify and extract key concepts, terms, themes, or formulas "
        "from the provided transcribed handwritten notes. "
        "For each concept, provide a concise definition, an exact supporting quote excerpt from the text, "
        "the source page number (from --- Page X ---), and related concepts mentioned. "
        "Return valid JSON adhering strictly to the requested schema."
    )

    prompt = f"""Extract 4 to 12 key concepts from the following transcribed notes.

NOTES CONTENT:
----------------
{full_notes}
----------------

SCHEMA REQUIREMENT:
Return a JSON object containing an array named "concepts":
{{
  "concepts": [
    {{
      "name": "Concept Name",
      "definition": "Clear, grounded definition based strictly on the text",
      "excerpt": "Direct supporting sentence or phrase from the notes",
      "page_number": 1,
      "related_concepts": ["Related Concept A", "Related Concept B"]
    }}
  ]
}}
"""

    logger.info(f"Extracting concepts for document #{document_id} with Ollama...")
    try:
        result = query_ollama_json(prompt=prompt, system_prompt=system_prompt, temperature=0.1)
    except OllamaError as oe:
        raise oe
    except Exception as e:
        logger.error(f"Concept extraction failed: {e}")
        raise RuntimeError(f"Concept extraction failed: {str(e)}")

    raw_concepts = result.get("concepts", [])
    if not isinstance(raw_concepts, list):
        if isinstance(result, list):
            raw_concepts = result
        else:
            raw_concepts = []

    # Clean existing concepts for this document
    db.query(HandwrittenConcept).filter(HandwrittenConcept.document_id == document_id).delete()
    db.flush()

    new_concepts = []
    for item in raw_concepts:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        definition = str(item.get("definition") or "").strip()
        excerpt = str(item.get("excerpt") or "").strip()
        try:
            page_num = int(item.get("page_number", 1))
        except (ValueError, TypeError):
            page_num = 1

        related = item.get("related_concepts") if isinstance(item.get("related_concepts"), list) else []

        if not name or not definition:
            continue

        is_bookmarked = name.lower() in bookmarked_names

        concept_obj = HandwrittenConcept(
            document_id=document_id,
            user_id=user_id,
            name=name,
            definition=definition,
            excerpt=excerpt,
            page_number=page_num,
            related_concepts=related,
            is_bookmarked=is_bookmarked,
            transcription_hash=current_hash
        )
        db.add(concept_obj)
        new_concepts.append(concept_obj)

    db.commit()

    return list_handwritten_concepts(document_id, user_id, db)


def list_handwritten_concepts(
    document_id: int,
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    List extracted concepts for a document with is_outdated status.
    """
    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    current_hash = source_data["hash"]

    concepts = (
        db.query(HandwrittenConcept)
        .filter(HandwrittenConcept.document_id == document_id)
        .order_by(HandwrittenConcept.is_bookmarked.desc(), HandwrittenConcept.id.asc())
        .all()
    )

    is_outdated = False
    items = []
    for c in concepts:
        if c.transcription_hash != current_hash:
            is_outdated = True
        items.append({
            "id": c.id,
            "document_id": c.document_id,
            "name": c.name,
            "definition": c.definition,
            "excerpt": c.excerpt,
            "page_number": c.page_number,
            "related_concepts": c.related_concepts or [],
            "is_bookmarked": c.is_bookmarked,
            "created_at": c.created_at.isoformat() if c.created_at else None
        })

    return {
        "concepts": items,
        "count": len(items),
        "is_outdated": is_outdated if current_hash and items else False,
        "has_transcription": source_data["has_transcription"]
    }


def toggle_concept_bookmark(
    concept_id: int,
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Toggle the bookmark state on an individual concept.
    """
    concept = (
        db.query(HandwrittenConcept)
        .filter(HandwrittenConcept.id == concept_id, HandwrittenConcept.user_id == user_id)
        .first()
    )
    if not concept:
        raise ValueError("Concept not found or access denied.")

    concept.is_bookmarked = not concept.is_bookmarked
    db.commit()
    db.refresh(concept)

    return {
        "id": concept.id,
        "is_bookmarked": concept.is_bookmarked
    }

