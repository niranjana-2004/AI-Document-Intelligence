import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.handwritten_analysis import HandwrittenFlashcardSet
from app.models.document import Document
from app.services.handwriting.handwritten_source_service import get_document_transcription_source
from app.services.handwriting.ollama_client import query_ollama_json, OllamaError

logger = logging.getLogger(__name__)

FLASHCARD_TYPES = [
    "question_answer",
    "term_definition",
    "concept_explanation",
    "formula_application",
    "problem_solution",
    "compare_contrast",
    "example_concept",
    "important_facts"
]


def generate_handwritten_flashcards(
    document_id: int,
    user_id: int,
    db: Session,
    card_count: int = 8,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate an interactive 3D flip flashcard deck across 8 pedagogical card types.
    """
    if card_count < 3 or card_count > 25:
        card_count = 8

    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    if not source_data["has_transcription"]:
        raise ValueError("Cannot generate flashcards: this document has no transcription yet.")

    full_notes = source_data["full_text"]
    current_hash = source_data["hash"]

    doc = db.query(Document).filter(Document.id == document_id).first()
    subject = (doc.subject if doc and doc.subject else None) or "General Academic"

    topic_prompt = ""
    if topic and topic.strip():
        topic_prompt = f"Focus the flashcards specifically around the theme/topic: '{topic.strip()}'."

    system_prompt = (
        f"You are an active-recall flashcard creator in {subject} for Cognidocs. "
        f"Create concise, high-yield study flashcards that encourage real memory retrieval of {subject} concepts and technical terminology. "
        "DIVERSITY REQUIREMENTS:\n"
        "Generate a diverse set spanning the following card types where applicable:\n"
        "1. question_answer: Active question on front, concise answer on back.\n"
        "2. term_definition: Term/vocabulary on front, accurate definition on back.\n"
        "3. concept_explanation: Concept name on front, clear mechanism/explanation on back.\n"
        "4. formula_application: Formula name on front, equation & variable breakdown on back.\n"
        "5. problem_solution: Short problem on front, step-by-step solution on back.\n"
        "6. compare_contrast: Two related ideas on front, key distinguishing difference on back.\n"
        "7. example_concept: A real-world example on front, which concept it demonstrates on back.\n"
        "8. important_facts: High-yield key fact prompt on front, memorization fact on back.\n"
        f"CRITICAL REQUIREMENT: You MUST generate EXACTLY {card_count} distinct flashcards in the 'cards' array. Do not generate only 1 card.\n"
        "RULES:\n"
        "- Do NOT make repetitive cards.\n"
        "- Front prompt must be punchy and direct.\n"
        "- Back answer must be clear, concise, and grounded strictly in the notes.\n"
        "- Include the source page number and quote excerpt for each card.\n"
        "- Output MUST strictly adhere to the requested JSON schema."
    )

    prompt = f"""Generate EXACTLY {card_count} active recall flashcards from the following transcribed notes.
{topic_prompt}

CRITICAL INSTRUCTION:
The "cards" array in your JSON output MUST contain exactly {card_count} cards (numbered card_1 to card_{card_count}).

NOTES CONTENT:
----------------
{full_notes}
----------------

SCHEMA REQUIREMENT:
Return a JSON object containing a "title" and a list of EXACTLY {card_count} "cards":
{{
  "title": "Topic or Deck Title",
  "cards": [
    {{
      "id": "card_1",
      "card_type": "term_definition",
      "topic": "Topic Name",
      "difficulty": "medium",
      "front": "Term or concept prompt",
      "back": "Precise answer or definition",
      "page_number": 1,
      "excerpt": "Supporting quote from the notes"
    }},
    {{
      "id": "card_2",
      "card_type": "qa",
      "topic": "Topic Name",
      "difficulty": "easy",
      "front": "Question prompt?",
      "back": "Clear concise answer",
      "page_number": 1,
      "excerpt": "Supporting quote from the notes"
    }}
  ]
}}
"""

    logger.info(f"Generating {card_count} advanced flashcards for doc #{document_id}...")
    try:
        result = query_ollama_json(prompt=prompt, system_prompt=system_prompt, temperature=0.18)
    except OllamaError as oe:
        raise oe
    except Exception as e:
        logger.error(f"Flashcard generation failed: {e}")
        raise RuntimeError(f"Flashcard generation failed: {str(e)}")

    title = str(result.get("title") or (f"{topic} Flashcards" if topic else "Active Recall Flashcards"))
    raw_cards = result.get("cards", [])
    if not isinstance(raw_cards, list):
        raw_cards = []

    cleaned_cards = []
    seen_fronts = set()

    for idx, c in enumerate(raw_cards):
        if not isinstance(c, dict):
            continue

        front = str(c.get("front") or "").strip()
        back = str(c.get("back") or "").strip()
        if not front or not back:
            continue

        # Deduplicate identical cards
        front_norm = re.sub(r'\W+', '', front.lower())
        if front_norm in seen_fronts:
            continue
        seen_fronts.add(front_norm)

        c_id = str(c.get("id") or f"c_{idx + 1}")
        c_type = str(c.get("card_type") or "concept_explanation").lower().strip()
        if c_type not in FLASHCARD_TYPES:
            c_type = "concept_explanation"

        c_topic = str(c.get("topic") or (topic if topic else "General Notes")).strip()
        c_diff = str(c.get("difficulty") or "medium").lower().strip()
        if c_diff not in ("easy", "medium", "hard"):
            c_diff = "medium"

        excerpt = str(c.get("excerpt") or "").strip()

        try:
            page_num = int(c.get("page_number", 1))
        except (ValueError, TypeError):
            page_num = 1

        cleaned_cards.append({
            "id": c_id,
            "card_type": c_type,
            "topic": c_topic,
            "difficulty": c_diff,
            "front": front,
            "back": back,
            "page_number": page_num,
            "excerpt": excerpt,
            "rating": None,  # 'again', 'hard', 'good', 'easy'
            "known": False,
            "needs_review": False,
            "review_count": 0,
            "last_reviewed_at": None
        })

    if not cleaned_cards:
        raise RuntimeError("Failed to generate valid flashcards from the notes.")

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
    status: Optional[str] = None,
    rating: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Update self-assessment rating and learning status for an individual card.
    Supports 4-level rating: 'again', 'hard', 'good', 'easy', or legacy 'known'/'needs_review'/'reset'.
    """
    query = db.query(HandwrittenFlashcardSet).filter(HandwrittenFlashcardSet.id == deck_id)
    if user_id is not None:
        query = query.filter(HandwrittenFlashcardSet.user_id == user_id)
    deck = query.first()

    if not deck:
        raise ValueError("Flashcard deck not found or access denied.")

    cards = list(deck.cards or [])
    card_found = False

    effective_rating = rating or status

    target_card = None
    for idx, c in enumerate(cards):
        if c.get("id") == card_id or str(idx) == str(card_id):
            card_found = True
            now_str = datetime.utcnow().isoformat()
            c["last_reviewed_at"] = now_str
            c["review_count"] = c.get("review_count", 0) + 1

            if effective_rating in ("again", "hard"):
                c["rating"] = effective_rating
                c["known"] = False
                c["needs_review"] = True
            elif effective_rating in ("good", "easy"):
                c["rating"] = effective_rating
                c["known"] = True
                c["needs_review"] = False
            elif effective_rating == "known":
                c["rating"] = "good"
                c["known"] = True
                c["needs_review"] = False
            elif effective_rating == "needs_review":
                c["rating"] = "hard"
                c["known"] = False
                c["needs_review"] = True
            elif effective_rating == "reset":
                c["rating"] = None
                c["known"] = False
                c["needs_review"] = False
                c["review_count"] = 0
            target_card = c
            break

    if not card_found:
        raise ValueError(f"Card {card_id} not found in deck {deck_id}.")

    deck.cards = cards
    flag_modified(deck, "cards")
    db.commit()
    db.refresh(deck)

    return {
        "message": "Card rating updated successfully",
        "card_id": card_id,
        "rating": effective_rating,
        "card": target_card
    }


def reset_deck_status(
    deck_id: int,
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Reset all cards in a deck to unreviewed state.
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
        c["rating"] = None
        c["review_count"] = 0

    deck.cards = cards
    flag_modified(deck, "cards")
    db.commit()
    db.refresh(deck)

    return {"message": "Deck reset successfully", "deck_id": deck_id}


def format_flashcard_response(record: HandwrittenFlashcardSet, current_hash: str) -> Dict[str, Any]:
    is_outdated = (record.transcription_hash != current_hash) if current_hash else False
    cards = record.cards or []

    topics = sorted(list({c.get("topic") for c in cards if c.get("topic")}))

    known_count = sum(1 for c in cards if c.get("known") or c.get("rating") in ("good", "easy"))
    review_count = sum(1 for c in cards if c.get("needs_review") or c.get("rating") in ("again", "hard"))
    unreviewed_count = sum(1 for c in cards if not c.get("rating") and not c.get("known") and not c.get("needs_review"))

    return {
        "id": record.id,
        "document_id": record.document_id,
        "title": record.title,
        "cards": cards,
        "topics": topics,
        "total_cards": len(cards),
        "card_count": len(cards),
        "known_count": known_count,
        "needs_review_count": review_count,
        "unreviewed_count": unreviewed_count,
        "transcription_hash": record.transcription_hash,
        "is_outdated": is_outdated,
        "created_at": record.created_at.isoformat() if record.created_at else None
    }
