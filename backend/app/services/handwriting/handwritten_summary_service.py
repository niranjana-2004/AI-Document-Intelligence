import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.handwritten_analysis import HandwrittenSummary
from app.models.document import Document
from app.services.handwriting.handwritten_source_service import get_document_transcription_source
from app.services.handwriting.ollama_client import query_ollama_json, OllamaError

logger = logging.getLogger(__name__)


def generate_handwritten_summary(
    document_id: int,
    user_id: int,
    db: Session,
    summary_type: str = "detailed"
) -> Dict[str, Any]:
    """
    Generate an AI-powered smart study summary grounded strictly in the transcribed handwritten notes.
    summary_type: 'quick' | 'detailed' | 'exam_revision'
    """
    if summary_type not in ("quick", "detailed", "exam_revision"):
        summary_type = "detailed"

    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    if not source_data["has_transcription"]:
        raise ValueError(
            "This document has no recognized transcription yet. "
            "Please run OCR or enter transcription in the Digital Transcription tab before generating a summary."
        )

    full_notes = source_data["full_text"]
    current_hash = source_data["hash"]

    doc = db.query(Document).filter(Document.id == document_id).first()
    subject = (doc.subject if doc and doc.subject else None) or "General Academic"

    # Prompt customization based on summary_type
    type_instructions = {
        "quick": (
            "Generate a concise executive summary focusing on the big picture, core thesis, and main 3-5 takeaways. "
            "Keep the overview brief (1-2 short paragraphs) and highlight immediate essentials."
        ),
        "detailed": (
            "Generate an exhaustive, structured study guide. Break down every topic into organized sections with clear "
            "markdown headings (## and ###). Include in-depth explanations, formulas/equations if present, and page citations "
            "like (Page X) for each key topic."
        ),
        "exam_revision": (
            "Generate a high-yield exam revision sheet. Emphasize must-know definitions, formulas, high-probability test questions, "
            "critical distinction points, and a rapid-recall memorization checklist. Group by priority for an exam."
        )
    }

    instruction = type_instructions.get(summary_type, type_instructions["detailed"])

    system_prompt = (
        f"You are an expert academic tutor in {subject} and document intelligence assistant for Cognidocs. "
        "Your task is to analyze transcribed handwritten student or lecture notes and synthesize a structured study guide. "
        "CRITICAL RULES:\n"
        "1. Strictly ground all content in the provided notes. Do NOT fabricate, speculate, or introduce external facts.\n"
        f"2. Maintain technical rigor, formulas, terminology, and definitions appropriate for {subject}.\n"
        "3. Note the page numbers provided in the notes headers (--- Page X ---) and cite them accurately.\n"
        "4. Output MUST be valid JSON adhering strictly to the requested schema."
    )

    prompt = f"""Analyze the following handwritten notes transcription and produce a {summary_type.upper()} study summary.

OBJECTIVE:
{instruction}

NOTES CONTENT:
----------------
{full_notes}
----------------

SCHEMA REQUIREMENT:
Return a JSON object with EXACTLY this structure:
{{
  "title": "A descriptive, clear title for this document's content",
  "overview": "A clear, well-written overview summarizing the document's main focus",
  "detailed_content": "Full markdown-formatted study notes with headers (##, ###), bullet points, explanations, and page citations",
  "takeaways": [
    "Key takeaway 1 with specific insight",
    "Key takeaway 2...",
    "Key takeaway 3..."
  ],
  "key_terms": [
    {{
      "term": "Term or concept name",
      "definition": "Precise definition grounded in the notes",
      "page_number": 1
    }}
  ]
}}
"""

    logger.info(f"Generating {summary_type} summary for document #{document_id} with Ollama...")
    try:
        result = query_ollama_json(prompt=prompt, system_prompt=system_prompt, temperature=0.15)
    except OllamaError as oe:
        raise oe
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        raise RuntimeError(f"Summary generation failed: {str(e)}")

    title = str(result.get("title") or f"Study Summary ({summary_type.capitalize()})")
    overview = str(result.get("overview") or "")
    detailed_content = str(result.get("detailed_content") or "")
    takeaways = result.get("takeaways") if isinstance(result.get("takeaways"), list) else []
    key_terms = result.get("key_terms") if isinstance(result.get("key_terms"), list) else []

    # Check for existing summary of this type for this document
    summary_record = (
        db.query(HandwrittenSummary)
        .filter(
            HandwrittenSummary.document_id == document_id,
            HandwrittenSummary.summary_type == summary_type
        )
        .first()
    )

    if not summary_record:
        summary_record = HandwrittenSummary(
            document_id=document_id,
            user_id=user_id,
            summary_type=summary_type,
            title=title,
            overview=overview,
            detailed_content=detailed_content,
            takeaways=takeaways,
            key_terms=key_terms,
            transcription_hash=current_hash
        )
        db.add(summary_record)
    else:
        summary_record.title = title
        summary_record.overview = overview
        summary_record.detailed_content = detailed_content
        summary_record.takeaways = takeaways
        summary_record.key_terms = key_terms
        summary_record.transcription_hash = current_hash

    db.commit()
    db.refresh(summary_record)

    return format_summary_response(summary_record, current_hash)


def get_handwritten_summary(
    document_id: int,
    user_id: int,
    db: Session,
    summary_type: str = "detailed"
) -> Optional[Dict[str, Any]]:
    """
    Retrieve existing summary for a document and compute is_outdated status.
    """
    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    current_hash = source_data["hash"]

    summary_record = (
        db.query(HandwrittenSummary)
        .filter(
            HandwrittenSummary.document_id == document_id,
            HandwrittenSummary.summary_type == summary_type
        )
        .first()
    )

    if not summary_record:
        return None

    return format_summary_response(summary_record, current_hash)


def format_summary_response(record: HandwrittenSummary, current_hash: str) -> Dict[str, Any]:
    is_outdated = (record.transcription_hash != current_hash) if current_hash else False
    return {
        "id": record.id,
        "document_id": record.document_id,
        "summary_type": record.summary_type,
        "title": record.title,
        "overview": record.overview,
        "detailed_content": record.detailed_content,
        "takeaways": record.takeaways or [],
        "key_terms": record.key_terms or [],
        "transcription_hash": record.transcription_hash,
        "is_outdated": is_outdated,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None
    }

