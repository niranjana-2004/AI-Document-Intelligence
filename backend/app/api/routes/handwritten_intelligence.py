import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.document import Document
from app.api.dependencies import get_current_user
from app.services.handwriting.handwritten_source_service import (
    get_document_transcription_source,
    sync_handwritten_chunks_and_embeddings
)
from app.services.handwriting.handwritten_summary_service import (
    generate_handwritten_summary,
    get_handwritten_summary
)
from app.services.handwriting.handwritten_concept_service import (
    generate_handwritten_concepts,
    list_handwritten_concepts,
    toggle_concept_bookmark
)
from app.services.handwriting.handwritten_quiz_service import (
    generate_handwritten_quiz,
    list_handwritten_quizzes,
    submit_quiz_answers
)
from app.services.handwriting.handwritten_flashcard_service import (
    generate_handwritten_flashcards,
    list_handwritten_flashcards,
    update_card_status,
    reset_deck_status
)
from app.services.handwriting.handwritten_chat_service import (
    ask_handwritten_notes,
    get_chat_history,
    clear_chat_history
)
from app.services.handwriting.ollama_client import OllamaError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/handwritten", tags=["Handwritten Intelligence (Phase 3)"])


# Request models
class GenerateSummaryRequest(BaseModel):
    summary_type: str = Field(default="detailed", description="quick, detailed, or exam_revision")


class GenerateQuizRequest(BaseModel):
    difficulty: str = Field(default="medium", description="easy, medium, or hard")
    question_count: int = Field(default=5, ge=1, le=15)
    question_types: str = Field(default="all", description="all, multiple_choice, true_false, short_answer")


class SubmitQuizRequest(BaseModel):
    answers: Dict[str, str] = Field(..., description="Mapping of question_id to selected answer")


class GenerateFlashcardsRequest(BaseModel):
    card_count: int = Field(default=8, ge=3, le=25)


class UpdateCardStatusRequest(BaseModel):
    status: str = Field(..., description="known, needs_review, or reset")


class ChatMessageRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


def _verify_document_ownership(document_id: int, user_id: int, db: Session) -> Document:
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.is_handwritten == True
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handwritten document not found or access denied."
        )
    return document


# ====================================================================
# SOURCE STATUS & OUTDATED DETECTION
# ====================================================================

@router.get("/{document_id}/intelligence-status")
def get_intelligence_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check transcription readiness, content hash, and whether analyses are outdated.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    source_data = get_document_transcription_source(document_id, db, user_id=current_user.id)
    return {
        "document_id": document_id,
        "has_transcription": source_data["has_transcription"],
        "total_pages": source_data["total_pages"],
        "transcribed_pages": source_data["transcribed_pages"],
        "content_hash": source_data["hash"]
    }


# ====================================================================
# FEATURE 1: SMART STUDY SUMMARY
# ====================================================================

@router.get("/{document_id}/summary")
def get_summary(
    document_id: int,
    type: str = Query("detailed", pattern="^(quick|detailed|exam_revision)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve existing summary for the requested mode.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    summary = get_handwritten_summary(document_id, current_user.id, db, summary_type=type)
    return {"summary": summary}


@router.post("/{document_id}/summary")
def generate_summary(
    document_id: int,
    body: GenerateSummaryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate or regenerate a smart study summary using local Ollama Llama 3.2.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        summary = generate_handwritten_summary(
            document_id=document_id,
            user_id=current_user.id,
            db=db,
            summary_type=body.summary_type
        )
        return {"message": "Summary generated successfully.", "summary": summary}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except OllamaError as oe:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(oe))
    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ====================================================================
# FEATURE 2: KEY CONCEPT EXTRACTION
# ====================================================================

@router.get("/{document_id}/concepts")
def get_concepts(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve extracted concepts for this document.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    return list_handwritten_concepts(document_id, current_user.id, db)


@router.post("/{document_id}/concepts/generate")
def generate_concepts(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extract structured concepts from the notes using Ollama.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        result = generate_handwritten_concepts(document_id, current_user.id, db)
        return {"message": "Concepts extracted successfully.", **result}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except OllamaError as oe:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(oe))
    except Exception as e:
        logger.error(f"Concept extraction error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.patch("/{document_id}/concepts/{concept_id}/bookmark")
def toggle_bookmark(
    document_id: int,
    concept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle bookmark status for an individual concept.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        return toggle_concept_bookmark(concept_id, current_user.id, db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


# ====================================================================
# FEATURE 3: AI QUIZ GENERATOR
# ====================================================================

@router.get("/{document_id}/quizzes")
def get_quizzes(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all generated quizzes for this document.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    quizzes = list_handwritten_quizzes(document_id, current_user.id, db)
    return {"quizzes": quizzes}


@router.post("/{document_id}/quizzes/generate")
def generate_quiz(
    document_id: int,
    body: GenerateQuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a new quiz set with configurable difficulty and question count.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        quiz = generate_handwritten_quiz(
            document_id=document_id,
            user_id=current_user.id,
            db=db,
            difficulty=body.difficulty,
            question_count=body.question_count,
            question_types=body.question_types
        )
        return {"message": "Quiz generated successfully.", "quiz": quiz}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except OllamaError as oe:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(oe))
    except Exception as e:
        logger.error(f"Quiz generation error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{document_id}/quizzes/{quiz_id}/submit")
def submit_quiz(
    document_id: int,
    quiz_id: int,
    body: SubmitQuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit user answers to a quiz, calculate score, and return detailed question feedback.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        result = submit_quiz_answers(
            quiz_id=quiz_id,
            answers=body.answers,
            user_id=current_user.id,
            db=db
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


# ====================================================================
# FEATURE 4: FLASHCARD GENERATOR
# ====================================================================

@router.get("/{document_id}/flashcards")
def get_flashcards(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all flashcard decks generated for this document.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    decks = list_handwritten_flashcards(document_id, current_user.id, db)
    return {"decks": decks}


@router.post("/{document_id}/flashcards/generate")
def generate_flashcards(
    document_id: int,
    body: GenerateFlashcardsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a new flashcard deck from handwritten notes.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        deck = generate_handwritten_flashcards(
            document_id=document_id,
            user_id=current_user.id,
            db=db,
            card_count=body.card_count
        )
        return {"message": "Flashcards generated successfully.", "deck": deck}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except OllamaError as oe:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(oe))
    except Exception as e:
        logger.error(f"Flashcard generation error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.patch("/{document_id}/flashcards/{deck_id}/cards/{card_id}")
def update_card(
    document_id: int,
    deck_id: int,
    card_id: str,
    body: UpdateCardStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update learning status for an individual card in a deck ('known', 'needs_review', 'reset').
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        return update_card_status(
            deck_id=deck_id,
            card_id=card_id,
            status=body.status,
            user_id=current_user.id,
            db=db
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/{document_id}/flashcards/{deck_id}/reset")
def reset_deck(
    document_id: int,
    deck_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reset all cards in a deck to unreviewed.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        return reset_deck_status(deck_id, current_user.id, db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


# ====================================================================
# FEATURE 5: CHAT WITH HANDWRITTEN NOTES (RAG)
# ====================================================================

@router.get("/{document_id}/chat/history")
def get_chat(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve message history for chatting with these handwritten notes.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    messages = get_chat_history(document_id, current_user.id, db)
    return {"messages": messages}


@router.post("/{document_id}/chat/message")
def send_chat_message(
    document_id: int,
    body: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Ask a question grounded strictly in the transcribed handwritten notes.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    try:
        return ask_handwritten_notes(
            document_id=document_id,
            question=body.question,
            user_id=current_user.id,
            db=db
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except OllamaError as oe:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(oe))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{document_id}/chat/history")
def clear_chat(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Clear conversation history for this document.
    """
    _verify_document_ownership(document_id, current_user.id, db)
    return clear_chat_history(document_id, current_user.id, db)
