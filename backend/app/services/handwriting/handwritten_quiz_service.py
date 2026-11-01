import logging
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.handwritten_analysis import HandwrittenQuizSet
from app.services.handwriting.handwritten_source_service import get_document_transcription_source
from app.services.handwriting.ollama_client import query_ollama_json, OllamaError

logger = logging.getLogger(__name__)


def generate_handwritten_quiz(
    document_id: int,
    user_id: int,
    db: Session,
    difficulty: str = "medium",
    question_count: int = 5,
    question_types: str = "all"
) -> Dict[str, Any]:
    """
    Generate an interactive quiz based on handwritten document transcription.
    difficulty: 'easy', 'medium', 'hard'
    question_count: 3 to 10
    question_types: 'all', 'multiple_choice', 'true_false', 'short_answer'
    """
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    if question_count < 1 or question_count > 15:
        question_count = 5

    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    if not source_data["has_transcription"]:
        raise ValueError("Cannot generate quiz: this document has no transcription yet.")

    full_notes = source_data["full_text"]
    current_hash = source_data["hash"]

    type_prompt = (
        "Include a balanced mix of multiple choice questions (with 4 options), "
        "True/False questions, and short-answer questions."
        if question_types == "all"
        else f"All questions must strictly be of type: {question_types}."
    )

    difficulty_prompt = {
        "easy": "Focus on straightforward recall of clearly stated facts, terms, and explicit statements.",
        "medium": "Test comprehension, relationships between concepts, and application of ideas found in the notes.",
        "hard": "Challenge depth of analysis, subtle distinctions, synthesizing across sections, and critical thinking."
    }.get(difficulty, "Test comprehension and core facts.")

    system_prompt = (
        "You are an assessment design expert. Create an educational quiz strictly grounded in the provided notes. "
        "Every single question must have a verifiable correct answer supported by the notes text. "
        "Include a clear explanation and cite the source page number and quote excerpt. "
        "Output MUST be valid JSON adhering strictly to the requested schema."
    )

    prompt = f"""Create a {difficulty.upper()} quiz containing {question_count} questions based on the following transcribed notes.

DIFFICULTY GUIDELINE:
{difficulty_prompt}

QUESTION TYPES:
{type_prompt}

NOTES CONTENT:
----------------
{full_notes}
----------------

SCHEMA REQUIREMENT:
Return a JSON object with:
{{
  "title": "Quiz Title describing the topic",
  "questions": [
    {{
      "id": "q1",
      "type": "multiple_choice",
      "question": "Clear question text?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "Detailed explanation of why this answer is correct based on the text",
      "excerpt": "Exact quote from notes proving the answer",
      "page_number": 1
    }},
    {{
      "id": "q2",
      "type": "true_false",
      "question": "Statement to evaluate as True or False?",
      "options": ["True", "False"],
      "correct_answer": "True",
      "explanation": "Why this statement is True or False according to notes",
      "excerpt": "Quote supporting this",
      "page_number": 1
    }}
  ]
}}
"""

    logger.info(f"Generating quiz ({difficulty}, count={question_count}) for doc #{document_id}...")
    try:
        result = query_ollama_json(prompt=prompt, system_prompt=system_prompt, temperature=0.2)
    except OllamaError as oe:
        raise oe
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        raise RuntimeError(f"Quiz generation failed: {str(e)}")

    title = str(result.get("title") or f"{difficulty.capitalize()} Quiz ({question_count} Questions)")
    raw_questions = result.get("questions", [])
    if not isinstance(raw_questions, list):
        raw_questions = []

    cleaned_questions = []
    for idx, q in enumerate(raw_questions):
        if not isinstance(q, dict):
            continue
        q_id = str(q.get("id") or f"q_{idx + 1}")
        q_type = str(q.get("type") or "multiple_choice")
        question_text = str(q.get("question") or "").strip()
        correct_ans = str(q.get("correct_answer") or "").strip()
        explanation = str(q.get("explanation") or "").strip()
        excerpt = str(q.get("excerpt") or "").strip()
        options = q.get("options") if isinstance(q.get("options"), list) else []

        try:
            page_num = int(q.get("page_number", 1))
        except (ValueError, TypeError):
            page_num = 1

        if not question_text:
            continue

        # If true_false, ensure options are ["True", "False"]
        if q_type == "true_false" and (not options or len(options) != 2):
            options = ["True", "False"]

        cleaned_questions.append({
            "id": q_id,
            "type": q_type,
            "question": question_text,
            "options": [str(opt) for opt in options],
            "correct_answer": correct_ans,
            "explanation": explanation,
            "excerpt": excerpt,
            "page_number": page_num
        })

    quiz_set = HandwrittenQuizSet(
        document_id=document_id,
        user_id=user_id,
        title=title,
        difficulty=difficulty,
        question_count=len(cleaned_questions),
        questions=cleaned_questions,
        transcription_hash=current_hash
    )
    db.add(quiz_set)
    db.commit()
    db.refresh(quiz_set)

    return format_quiz_response(quiz_set, current_hash)


def list_handwritten_quizzes(
    document_id: int,
    user_id: int,
    db: Session
) -> List[Dict[str, Any]]:
    """
    List all quiz sets generated for a document.
    """
    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    current_hash = source_data["hash"]

    quizzes = (
        db.query(HandwrittenQuizSet)
        .filter(HandwrittenQuizSet.document_id == document_id)
        .order_by(HandwrittenQuizSet.created_at.desc())
        .all()
    )

    return [format_quiz_response(q, current_hash) for q in quizzes]


def submit_quiz_answers(
    quiz_id: int,
    answers: Dict[str, str],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Evaluate user's submitted answers, compute final score, and return breakdown.
    """
    quiz = (
        db.query(HandwrittenQuizSet)
        .filter(HandwrittenQuizSet.id == quiz_id, HandwrittenQuizSet.user_id == user_id)
        .first()
    )
    if not quiz:
        raise ValueError("Quiz not found or access denied.")

    questions = quiz.questions or []
    total = len(questions)
    correct_count = 0
    feedback = []

    for q in questions:
        q_id = q.get("id")
        user_ans = str(answers.get(q_id, "")).strip().lower()
        corr_ans = str(q.get("correct_answer", "")).strip().lower()

        # Handle simple string equality or substring match for short answers
        if q.get("type") in ("multiple_choice", "true_false"):
            is_correct = (user_ans == corr_ans) or (
                corr_ans.startswith(user_ans[:1]) and len(user_ans) == 1
            )
        else:
            is_correct = (user_ans == corr_ans) or (corr_ans in user_ans) or (user_ans in corr_ans and len(user_ans) > 3)

        if is_correct:
            correct_count += 1

        feedback.append({
            "id": q_id,
            "question": q.get("question"),
            "user_answer": answers.get(q_id, ""),
            "correct_answer": q.get("correct_answer"),
            "is_correct": is_correct,
            "explanation": q.get("explanation"),
            "excerpt": q.get("excerpt"),
            "page_number": q.get("page_number")
        })

    quiz.user_score = correct_count
    quiz.user_answers = answers
    db.commit()
    db.refresh(quiz)

    percentage = round((correct_count / total * 100), 1) if total > 0 else 0

    return {
        "quiz_id": quiz.id,
        "total_questions": total,
        "correct_count": correct_count,
        "score_percentage": percentage,
        "feedback": feedback
    }


def format_quiz_response(record: HandwrittenQuizSet, current_hash: str) -> Dict[str, Any]:
    is_outdated = (record.transcription_hash != current_hash) if current_hash else False
    return {
        "id": record.id,
        "document_id": record.document_id,
        "title": record.title,
        "difficulty": record.difficulty,
        "question_count": record.question_count,
        "questions": record.questions or [],
        "user_score": record.user_score,
        "user_answers": record.user_answers,
        "transcription_hash": record.transcription_hash,
        "is_outdated": is_outdated,
        "created_at": record.created_at.isoformat() if record.created_at else None
    }

