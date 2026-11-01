import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.handwritten_analysis import HandwrittenQuizSet, HandwrittenConcept
from app.services.handwriting.handwritten_source_service import get_document_transcription_source
from app.services.handwriting.ollama_client import query_ollama_json, OllamaError

logger = logging.getLogger(__name__)

# Valid pedagogical categories
QUESTION_CATEGORIES = [
    "conceptual",
    "definition",
    "application",
    "scenario",
    "analytical",
    "comparison",
    "problem_solving"
]


def get_document_topics(
    document_id: int,
    user_id: int,
    db: Session
) -> List[str]:
    """
    Extract unique academic topics and concepts available in the document.
    """
    topics = set()

    # 1. Check extracted concepts
    concepts = (
        db.query(HandwrittenConcept)
        .filter(HandwrittenConcept.document_id == document_id)
        .all()
    )
    for c in concepts:
        if c.name:
            topics.add(c.name.strip())

    # 2. Check previous quizzes
    quizzes = (
        db.query(HandwrittenQuizSet)
        .filter(HandwrittenQuizSet.document_id == document_id)
        .all()
    )
    for q in quizzes:
        for item in (q.questions or []):
            if isinstance(item, dict) and item.get("topic"):
                topics.add(item["topic"].strip())

    return sorted(list(topics)) if topics else ["General Notes", "Core Concepts"]


def _calculate_word_jaccard(str1: str, str2: str) -> float:
    """Calculate word overlap similarity to detect duplicate questions."""
    w1 = set(re.findall(r'\w+', str1.lower()))
    w2 = set(re.findall(r'\w+', str2.lower()))
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def generate_handwritten_quiz(
    document_id: int,
    user_id: int,
    db: Session,
    difficulty: str = "medium",
    question_count: int = 5,
    question_types: str = "all",
    topics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Generate an advanced, subject-aware, non-repetitive examination quiz.
    difficulty: 'easy' | 'medium' | 'hard' | 'mixed'
    question_count: 3 to 15
    question_types: 'all' | 'multiple_choice' | 'true_false' | 'short_answer'
    topics: Optional filter to focus questions on specific topics
    """
    if difficulty not in ("easy", "medium", "hard", "mixed"):
        difficulty = "medium"
    if question_count < 1 or question_count > 15:
        question_count = 5

    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    if not source_data["has_transcription"]:
        raise ValueError("Cannot generate quiz: this document has no transcription yet.")

    full_notes = source_data["full_text"]
    current_hash = source_data["hash"]

    # Build topic guidance if specified
    topic_clause = ""
    if topics and len(topics) > 0:
        valid_topics = [t.strip() for t in topics if t.strip()]
        if valid_topics:
            topic_clause = f"Focus questions specifically on the following topics: {', '.join(valid_topics)}."

    # Build type instructions
    if question_types == "multiple_choice":
        type_prompt = "All questions must strictly be Multiple Choice Questions (with exactly 4 distinct options)."
    elif question_types == "true_false":
        type_prompt = "All questions must strictly be True or False statements (options: ['True', 'False'])."
    elif question_types == "short_answer":
        type_prompt = "All questions must strictly be Short-Answer recall questions (options: [])."
    else:
        type_prompt = (
            "Provide a diverse, balanced mix of Multiple Choice Questions (with 4 distinct options), "
            "True or False statements, and Short-Answer questions."
        )

    # Build difficulty guidelines
    if difficulty == "mixed":
        diff_prompt = (
            "Distribute difficulty across questions: include 30% Easy (factual recall), "
            "50% Medium (application & analytical), and 20% Hard (comparison & problem-solving)."
        )
    elif difficulty == "easy":
        diff_prompt = "All questions should test straightforward recall of clearly stated facts, definitions, and formulas."
    elif difficulty == "medium":
        diff_prompt = "All questions should test comprehension, relationships between concepts, and application."
    else:
        diff_prompt = "All questions should challenge deep analytical synthesis, subtle distinctions, and critical reasoning."

    system_prompt = (
        "You are an elite academic examination board creating an interactive test based on handwritten student notes. "
        f"CRITICAL REQUIREMENT: You MUST generate EXACTLY {question_count} distinct questions in the 'questions' array. Do not stop early or generate only 1 question.\n"
        "STRICT PEDAGOGICAL CRITERIA:\n"
        "1. Every question must be directly grounded in the provided notes. Never invent claims or hallucinate.\n"
        "2. Avoid repetitive questions: each question MUST test a DIFFERENT concept or detail.\n"
        "3. Incorporate diverse question categories: conceptual, definition, application, scenario, analytical, comparison, problem_solving.\n"
        "4. For Multiple Choice Questions, provide 4 distinctly different, plausible options. The correct answer must be unambiguous.\n"
        "5. Provide the exact source page number (from --- Page X ---) and a direct quote excerpt supporting the answer.\n"
        "6. Output MUST strictly adhere to the requested JSON schema."
    )

    prompt = f"""Generate an advanced examination quiz containing EXACTLY {question_count} distinct questions based on these notes.

CRITICAL INSTRUCTION:
The "questions" array in your JSON output MUST contain exactly {question_count} questions (numbered q1 to q{question_count}). Do NOT return fewer than {question_count} items.

EXAMINATION REQUIREMENTS:
- Question Distribution: {diff_prompt}
- Question Formats: {type_prompt}
{topic_clause}

CATEGORIES TO USE:
Ensure questions span conceptual understanding, definition, application, scenario-based, analytical, comparison, and problem-solving where appropriate.

NOTES CONTENT:
----------------
{full_notes}
----------------

SCHEMA REQUIREMENT:
Return valid JSON with:
{{
  "title": "Clear descriptive title for this examination",
  "questions": [
    {{
      "id": "q1",
      "type": "multiple_choice",
      "category": "conceptual",
      "difficulty": "easy",
      "topic": "Topic Name",
      "question": "Question 1 text?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "Why correct based on notes",
      "excerpt": "Quote from notes",
      "page_number": 1
    }},
    {{
      "id": "q2",
      "type": "true_false",
      "category": "analytical",
      "difficulty": "medium",
      "topic": "Topic Name",
      "question": "Question 2 statement?",
      "options": ["True", "False"],
      "correct_answer": "True",
      "explanation": "Why correct based on notes",
      "excerpt": "Quote from notes",
      "page_number": 1
    }}
  ]
}}
"""

    logger.info(f"Generating advanced quiz ({difficulty}, count={question_count}) for doc #{document_id}...")
    try:
        result = query_ollama_json(prompt=prompt, system_prompt=system_prompt, temperature=0.18)
    except OllamaError as oe:
        raise oe
    except Exception as e:
        logger.error(f"Advanced quiz generation failed: {e}")
        raise RuntimeError(f"Quiz generation failed: {str(e)}")

    title = str(result.get("title") or f"{difficulty.capitalize()} Examination ({question_count} Questions)")
    raw_questions = result.get("questions", [])
    if not isinstance(raw_questions, list):
        raw_questions = []

    # Process and validate questions with deduplication & quality safeguards
    cleaned_questions = []
    seen_prompts = []

    for idx, q in enumerate(raw_questions):
        if not isinstance(q, dict):
            continue

        q_text = str(q.get("question") or "").strip()
        correct_ans = str(q.get("correct_answer") or "").strip()
        if not q_text or not correct_ans:
            continue

        # Safeguard 1: Duplicate check (Jaccard similarity > 0.70)
        is_dup = any(_calculate_word_jaccard(q_text, seen) > 0.70 for seen in seen_prompts)
        if is_dup:
            logger.info(f"Skipping duplicate question: {q_text}")
            continue

        seen_prompts.append(q_text)

        q_id = str(q.get("id") or f"q_{idx + 1}")
        q_type = str(q.get("type") or "multiple_choice")
        if q_type not in ("multiple_choice", "true_false", "short_answer"):
            q_type = "multiple_choice"

        q_category = str(q.get("category") or "conceptual")
        if q_category not in QUESTION_CATEGORIES:
            q_category = "conceptual"

        q_difficulty = str(q.get("difficulty") or (difficulty if difficulty != "mixed" else "medium"))
        if q_difficulty not in ("easy", "medium", "hard"):
            q_difficulty = "medium"

        q_topic = str(q.get("topic") or "General Review").strip()
        explanation = str(q.get("explanation") or "").strip()
        excerpt = str(q.get("excerpt") or "").strip()

        try:
            page_num = int(q.get("page_number", 1))
        except (ValueError, TypeError):
            page_num = 1

        # Safeguard 2: Clean options & ensure distinctness
        raw_options = q.get("options") if isinstance(q.get("options"), list) else []
        options = []
        if q_type == "multiple_choice":
            # Distinct options only
            seen_opts = set()
            for opt in raw_options:
                opt_str = str(opt).strip()
                if opt_str and opt_str not in seen_opts:
                    seen_opts.add(opt_str)
                    options.append(opt_str)

            # Ensure correct answer is in options
            if correct_ans not in options and len(options) > 0:
                options[0] = correct_ans
            elif not options:
                options = [correct_ans, "Alternative A", "Alternative B", "Alternative C"]

        elif q_type == "true_false":
            options = ["True", "False"]
            if correct_ans.lower() in ("true", "t"):
                correct_ans = "True"
            else:
                correct_ans = "False"
        else:
            options = []

        cleaned_questions.append({
            "id": q_id,
            "type": q_type,
            "category": q_category,
            "difficulty": q_difficulty,
            "topic": q_topic,
            "question": q_text,
            "options": options,
            "correct_answer": correct_ans,
            "explanation": explanation,
            "excerpt": excerpt,
            "page_number": page_num
        })

    if not cleaned_questions:
        raise RuntimeError("Failed to generate valid examination questions from the notes.")

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
    List all quiz sets for a document. Unsubmitted quizzes hide answers.
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
    time_taken_seconds: Optional[int],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Evaluate user's submitted answers, compute detailed metrics,
    identify weak topics, and generate targeted recommendations.
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
    incorrect_count = 0
    unanswered_count = 0
    feedback = []
    topic_performance = {}  # topic -> {total: X, correct: Y, pages: set()}

    for q in questions:
        q_id = q.get("id")
        user_ans = str(answers.get(q_id, "")).strip()
        corr_ans = str(q.get("correct_answer", "")).strip()
        topic = str(q.get("topic") or "General").strip()
        page_num = q.get("page_number", 1)

        if topic not in topic_performance:
            topic_performance[topic] = {"total": 0, "correct": 0, "pages": set()}
        topic_performance[topic]["total"] += 1
        topic_performance[topic]["pages"].add(page_num)

        if not user_ans:
            # Question was skipped / left unanswered
            is_unanswered = True
            is_correct = False
            unanswered_count += 1
        else:
            is_unanswered = False
            # Check correctness
            u_clean = user_ans.lower()
            c_clean = corr_ans.lower()

            if q.get("type") in ("multiple_choice", "true_false"):
                is_correct = (u_clean == c_clean) or (
                    c_clean.startswith(u_clean[:1]) and len(u_clean) == 1
                )
            else:
                # Short answer match
                is_correct = (u_clean == c_clean) or (c_clean in u_clean) or (u_clean in c_clean and len(u_clean) > 3)

            if is_correct:
                correct_count += 1
                topic_performance[topic]["correct"] += 1
            else:
                incorrect_count += 1

        feedback.append({
            "id": q_id,
            "type": q.get("type"),
            "category": q.get("category"),
            "difficulty": q.get("difficulty"),
            "topic": topic,
            "question": q.get("question"),
            "options": q.get("options", []),
            "user_answer": user_ans,
            "correct_answer": corr_ans,
            "is_correct": is_correct,
            "is_unanswered": is_unanswered,
            "explanation": q.get("explanation"),
            "excerpt": q.get("excerpt"),
            "page_number": page_num
        })

    percentage = round((correct_count / total * 100), 1) if total > 0 else 0

    # Step 6: Identify Weak Topics & Recommendations
    weak_topics = []
    recommendations = []

    for top, stats in topic_performance.items():
        top_tot = stats["total"]
        top_corr = stats["correct"]
        top_pct = round((top_corr / top_tot * 100), 1)
        sorted_pages = sorted(list(stats["pages"]))

        if top_pct < 75.0 or (top_tot - top_corr) > 0:
            weak_topics.append({
                "topic": top,
                "score_percentage": top_pct,
                "missed_count": top_tot - top_corr,
                "total_questions": top_tot,
                "pages": sorted_pages
            })
            recommendations.append({
                "topic": top,
                "action": f"Re-read notes on {top} (Page {', '.join(map(str, sorted_pages))})",
                "flashcard_suggestion": f"Practice flashcards tagged with '{top}'",
                "pages": sorted_pages
            })

    # Save to database
    quiz.user_score = correct_count
    quiz.user_answers = answers
    if time_taken_seconds is not None:
        quiz.time_taken_seconds = time_taken_seconds
    quiz.weak_topics = weak_topics
    quiz.recommendations = recommendations

    flag_modified(quiz, "user_answers")
    flag_modified(quiz, "weak_topics")
    flag_modified(quiz, "recommendations")
    db.commit()
    db.refresh(quiz)

    # Performance summary message
    if percentage >= 90:
        perf_summary = "Outstanding mastery! You have demonstrated exceptional command of these notes."
    elif percentage >= 75:
        perf_summary = "Strong understanding. A few targeted areas can be strengthened with review."
    elif percentage >= 50:
        perf_summary = "Fair effort. Review the weak topics highlighted below before re-testing."
    else:
        perf_summary = "Needs further revision. Re-read the source pages indicated and practice flashcards."

    return {
        "quiz_id": quiz.id,
        "total_questions": total,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unanswered_count": unanswered_count,
        "score_percentage": percentage,
        "time_taken_seconds": quiz.time_taken_seconds,
        "performance_summary": perf_summary,
        "feedback": feedback,
        "weak_topics": weak_topics,
        "recommendations": recommendations
    }


def format_quiz_response(record: HandwrittenQuizSet, current_hash: str) -> Dict[str, Any]:
    """
    Format quiz response.
    CRITICAL: Never reveal correct_answer, explanation, or excerpt if user has not submitted!
    """
    is_outdated = (record.transcription_hash != current_hash) if current_hash else False
    is_submitted = record.user_answers is not None and record.user_score is not None

    sanitized_questions = []
    for q in (record.questions or []):
        if not isinstance(q, dict):
            continue

        item = {
            "id": q.get("id"),
            "type": q.get("type", "multiple_choice"),
            "category": q.get("category", "conceptual"),
            "difficulty": q.get("difficulty", "medium"),
            "topic": q.get("topic", "General"),
            "question": q.get("question"),
            "options": q.get("options", []),
            "page_number": q.get("page_number", 1)
        }

        # ONLY reveal answers and explanations if the quiz was already submitted!
        if is_submitted:
            item["correct_answer"] = q.get("correct_answer")
            item["explanation"] = q.get("explanation")
            item["excerpt"] = q.get("excerpt")

        sanitized_questions.append(item)

    return {
        "id": record.id,
        "document_id": record.document_id,
        "title": record.title,
        "difficulty": record.difficulty,
        "question_count": record.question_count,
        "questions": sanitized_questions,
        "is_submitted": is_submitted,
        "user_score": record.user_score if is_submitted else None,
        "user_answers": record.user_answers if is_submitted else None,
        "time_taken_seconds": getattr(record, "time_taken_seconds", None) if is_submitted else None,
        "weak_topics": getattr(record, "weak_topics", None) if is_submitted else None,
        "recommendations": getattr(record, "recommendations", None) if is_submitted else None,
        "transcription_hash": record.transcription_hash,
        "is_outdated": is_outdated,
        "created_at": record.created_at.isoformat() if record.created_at else None
    }
