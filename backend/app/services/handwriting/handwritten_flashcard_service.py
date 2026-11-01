import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.handwritten_analysis import HandwrittenFlashcardSet
from app.services.handwriting.handwritten_source_service import get_document_transcription_source
from app.services.handwriting.ollama_client import query_ollama_json, OllamaError

logger = logging.getLogger(__name__)


def generate_handwritten_flashcards(
    document_id: int,
    user_id: int,
    db: Session,
    card_count: int = 8
) -> Dict[str, Any]:
    """
    Generate an interactive 3D flip flashcard deck from transcribed handwritten notes.
    """
    if card_count < 3 or card_count > 25:
        card_count = 8

    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    if not source_data["has_transcription"]:
        raise ValueError("Cannot generate flashcards: this document has no transcription yet.")

    full_notes = source_data["full_text"]
    current_hash = source_data["hash"]

    system_prompt = (
        "You are an active recall flashcard creator. "
        "Create concise, high-yield study flashcards based on the provided transcribed notes. "
        "The 'front' should be a clear prompt, term, or question. "
        "The 'back' should be a punchy, precise answer or definition, along with the source page number. "
        "Return valid JSON adhering strictly to the requested schema."
    )

    prompt = f"""Generate {card_count} active recall flashcards from the following transcribed notes.

NOTES CONTENT:
----------------
{full_notes}
----------------

SCHEMA REQUIREMENT:
Return a JSON object containing a "title" and a list of "cards":
{{
  "title": "Flashcard Deck Title",
  "cards": [
    {{
      "id": "card_1",
      "front": "Term, Concept, or Question",
      "back": "Direct, clear answer or definition",
      "page_number": 1
    }}
  ]
}}
"""

    logger.info(f"Generating {card_count} flashcards for doc #{document_id}...")
    try:
        result = query_ollama_json(prompt=prompt, system_prompt=system_prompt, temperature=0.15)
    except OllamaError as oe:
        raise oe
    except Exception as e:
        logger.error(f"Flashcard generation failed: {e}")
        raise RuntimeError(f"Flashcard generation failed: {str(e)}")

    title = str(result.get("title") or "Study Flashcards")
    raw_cards = result.get("cards", [])
    if not isinstance(raw_cards, list):
        raw_cards = []

    cleaned_cards = []
    for idx, c in enumerate(raw_cards):
        if not isinstance(c, dict):
            continue
        c_id = str(c.get("id") or f"c_{idx + 1}")
        front = str(c.get("front") or "").strip()
        back = str(c.get("back") or "").strip()
        try:
            page_num = int(c.get("page_number", 1))
        except (ValueError, TypeError):
            page_num = 1

        if not front or not back:
            continue

        cleaned_cards.append({
            "id": c_id,
            "front": front,
            "back": back,
            "page_number": page_num,
            "known": False,
            "needs_review": False
        })

    deck = HandwrittenFlashcardSet(
        document_id=document_id,
        user_id=user_id,
        title=title,
        cards=cleaned_cards,
        transcription_hash=current_hash
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)

    return format_flashcard_response(deck, current_hash)


def list_handwritten_flashcards(
    document_id: int,
    user_id: int,
    db: Session
) -> List[Dict[str, Any]]:
    """
    List all flashcard decks for a document.
    """
    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    current_hash = source_data["hash"]

    decks = (
        db.query(HandwrittenFlashcardSet)
        .filter(HandwrittenFlashcardSet.document_id == document_id)
        .order_by(HandwrittenFlashcardSet.created_at.desc())
        .all()
    )

    return [format_flashcard_response(d, current_hash) for d in decks]


def update_card_status(
    deck_id: int,
    card_id: str,
    status: str,  # 'known', 'needs_review', or 'reset'
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Update learning status for an individual card in a deck.
    """
    deck = (
        db.query(HandwrittenFlashcardSet)
        .filter(HandwrittenFlashcardSet.id == deck_id, HandwrittenFlashcardSet.user_id == user_id)
        .first()
    )
    if not deck:
        raise ValueError("Flashcard deck not found or access denied.")

    cards = list(deck.cards or [])
    card_found = False

    for c in cards:
        if c.get("id") == card_id:
            card_found = True
            if status == "known":
                c["known"] = True
                c["needs_review"] = False
            elif status == "needs_review":
                c["known"] = False
                c["needs_review"] = True
            elif status == "reset":
                c["known"] = False
                c["needs_review"] = False
            break

    if not card_found:
        raise ValueError(f"Card {card_id} not found in deck {deck_id}.")

    deck.cards = cards
    # Force SQLAlchemy to notice JSON modification
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(deck, "cards")

    db.commit()
    db.refresh(deck)

    return {"message": "Card status updated", "card_id": card_id, "status": status}


def reset_deck_status(
    deck_id: int,
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Reset all cards in a deck to unreviewed.
    """
    deck = (
        db.query(HandwrittenFlashcardSet)
        .filter(HandwrittenFlashcardSet.id == deck_id, HandwrittenFlashcardSet.user_id == user_id)
        .first()
    )
    if not deck:
        raise ValueError("Deck not found or access denied.")

    cards = list(deck.cards or [])
    for c in cards:
        c["known"] = False
        c["needs_review"] = False

    deck.cards = cards
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(deck, "cards")

    db.commit()
    db.refresh(deck)

    return {"message": "Deck reset successfully", "deck_id": deck_id}


def format_flashcard_response(record: HandwrittenFlashcardSet, current_hash: str) -> Dict[str, Any]:
    is_outdated = (record.transcription_hash != current_hash) if current_hash else False
    cards = record.cards or []
    known_count = sum(1 for c in cards if c.get("known"))
    review_count = sum(1 for c in cards if c.get("needs_review"))

    return {
        "id": record.id,
        "document_id": record.document_id,
        "title": record.title,
        "cards": cards,
        "total_cards": len(cards),
        "known_count": known_count,
        "needs_review_count": review_count,
        "transcription_hash": record.transcription_hash,
        "is_outdated": is_outdated,
        "created_at": record.created_at.isoformat() if record.created_at else None
    }

