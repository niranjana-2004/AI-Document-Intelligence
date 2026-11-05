import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.handwritten_analysis import HandwrittenChatSession, HandwrittenChatMessage
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.handwriting.handwritten_source_service import (
    get_document_transcription_source,
    sync_handwritten_chunks_and_embeddings
)
from app.services.search_service import semantic_search
from app.services.handwriting.ollama_client import query_ollama, OllamaError

logger = logging.getLogger(__name__)

FALLBACK_NOTE_ANSWER = (
    "I could not find information about that in these handwritten notes. "
    "Please ask a question related to the transcribed content or review the notes in the Transcription tab."
)


def get_or_create_chat_session(
    document_id: int,
    user_id: int,
    db: Session
) -> HandwrittenChatSession:
    """
    Get or create an active chat session for a handwritten document.
    """
    session = (
        db.query(HandwrittenChatSession)
        .filter(
            HandwrittenChatSession.document_id == document_id,
            HandwrittenChatSession.user_id == user_id
        )
        .first()
    )

    if not session:
        session = HandwrittenChatSession(
            document_id=document_id,
            user_id=user_id,
            title=f"Chat on Document #{document_id}"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    return session


def ask_handwritten_notes(
    document_id: int,
    question: str,
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Document-grounded RAG chat against transcribed handwritten notes.
    Retrieves matching chunks, formats prompt with page citations, queries Ollama,
    and records interaction in chat history.
    """
    question_clean = question.strip()
    if not question_clean:
        raise ValueError("Question cannot be empty.")

    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    if not source_data["has_transcription"]:
        return {
            "answer": "This document has no recognized transcription yet. Please run OCR or type transcription in the Digital Transcription tab before chatting.",
            "sources": []
        }

    # Ensure document chunks exist and are synced
    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
    if chunk_count == 0:
        logger.info(f"Indexing chunks for handwritten doc #{document_id} before chat...")
        sync_handwritten_chunks_and_embeddings(document_id, db)

    # 1. Retrieve relevant chunks via hybrid search
    results = semantic_search(
        query=question_clean,
        db=db,
        document_id=document_id,
        user_id=user_id,
        top_k=4
    )

    context_snippets = []
    sources = []

    if results:
        for idx, res in enumerate(results, start=1):
            chunk = res.get("chunk")
            page_num = chunk.page_number if chunk and chunk.page_number else 1
            content = chunk.content if chunk else res.get("content", "")
            excerpt = content[:200] + ("..." if len(content) > 200 else "")

            context_snippets.append(f"[Source {idx} | Page {page_num}]\n{content}")
            sources.append({
                "source_index": idx,
                "page_number": page_num,
                "excerpt": excerpt
            })
    else:
        # Fallback to full notes if short or first page
        for p in source_data["pages"]:
            if p["text"]:
                context_snippets.append(f"[Source {p['page_number']} | Page {p['page_number']}]\n{p['text']}")
                sources.append({
                    "source_index": p["page_number"],
                    "page_number": p["page_number"],
                    "excerpt": p["text"][:200]
                })

    context_str = "\n\n".join(context_snippets)

    # 2. Get recent conversation turns for context
    chat_session = get_or_create_chat_session(document_id, user_id, db)
    recent_msgs = (
        db.query(HandwrittenChatMessage)
        .filter(HandwrittenChatMessage.session_id == chat_session.id)
        .order_by(HandwrittenChatMessage.created_at.desc())
        .limit(6)
        .all()
    )
    recent_msgs.reverse()

    history_str = ""
    if recent_msgs:
        formatted_history = []
        for m in recent_msgs:
            speaker = "User" if m.role == "user" else "Assistant"
            formatted_history.append(f"{speaker}: {m.content}")
        history_str = "PREVIOUS CONVERSATION:\n" + "\n".join(formatted_history) + "\n\n"

    doc = db.query(Document).filter(Document.id == document_id).first()
    subject = (doc.subject if doc and doc.subject else None) or "General Academic"

    system_prompt = (
        f"You are Cognidocs AI, a specialized academic tutor in {subject} answering questions about a student's handwritten notes. "
        "Strict rules:\n"
        "1. Ground your answer EXCLUSIVELY in the provided NOTES CONTEXT below.\n"
        f"2. Maintain technical rigor, formulas, terminology, and definitions appropriate for {subject}.\n"
        "3. When stating facts, cite the page number like [Page X] or (Page X).\n"
        "4. Do not make up facts or use outside knowledge not supported by the notes.\n"
        f"5. If the notes do not mention or provide enough information, say: '{FALLBACK_NOTE_ANSWER}'\n"
        "6. Keep responses concise, clear, and easy to study."
    )

    prompt = f"""{history_str}NOTES CONTEXT:
----------------
{context_str}
----------------

USER QUESTION:
{question_clean}

ANSWER (grounded in the notes above):"""

    logger.info(f"Querying Ollama for handwritten notes chat doc #{document_id}...")
    try:
        answer = query_ollama(prompt=prompt, system_prompt=system_prompt, temperature=0.2)
    except OllamaError as oe:
        raise oe
    except Exception as e:
        logger.error(f"Chat generation failed: {e}")
        raise RuntimeError(f"Chat generation failed: {str(e)}")

    if not answer.strip():
        answer = FALLBACK_NOTE_ANSWER

    # Record user message & assistant answer in database
    user_msg = HandwrittenChatMessage(
        session_id=chat_session.id,
        role="user",
        content=question_clean
    )
    db.add(user_msg)

    asst_msg = HandwrittenChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content=answer,
        sources=sources
    )
    db.add(asst_msg)
    db.commit()

    return {
        "answer": answer,
        "sources": sources,
        "session_id": chat_session.id
    }


def get_chat_history(
    document_id: int,
    user_id: int,
    db: Session
) -> List[Dict[str, Any]]:
    """
    Retrieve message history for the handwritten document's chat session.
    """
    session = get_or_create_chat_session(document_id, user_id, db)
    messages = (
        db.query(HandwrittenChatMessage)
        .filter(HandwrittenChatMessage.session_id == session.id)
        .order_by(HandwrittenChatMessage.created_at.asc())
        .all()
    )

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources or [],
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in messages
    ]


def clear_chat_history(
    document_id: int,
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Clear all messages in the chat session for this document.
    """
    session = get_or_create_chat_session(document_id, user_id, db)
    db.query(HandwrittenChatMessage).filter(HandwrittenChatMessage.session_id == session.id).delete()
    db.commit()
    return {"message": "Chat history cleared successfully."}

