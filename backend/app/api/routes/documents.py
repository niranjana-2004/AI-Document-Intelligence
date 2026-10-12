from app.core import database
from dns import asyncquery
from app.core import database
from pathlib import Path

# pyrefly: ignore [missing-import]
from app.services.document_service import process_document
from app.core.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.search_service import semantic_search
from app.services.question_service import answer_question, get_document_suggested_questions
from app.schemas.question import QuestionRequest, SuggestedQuestionsRequest, SuggestedQuestionsResponse
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import cast
from app.services.llm_service import (
    generate_summary,
    LLMServiceError,
    LLMConnectionError,
    LLMTimeoutError
)
from app.services.text_processing_service import detect_chunk_category
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.activity import ActivityLog
from app.models.conversation import Conversation, ConversationMessage

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/")
def get_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    documents = (
    db.query(Document)
    .filter(Document.user_id == current_user.id)
    .all()
)

    return {
        "count": len(documents),
        "documents": [
            {
                "id": document.id,
                "filename": document.filename,
                "document_type": document.document_type,
                "text_length": document.text_length,
                "created_at": document.created_at
            }
            for document in documents
        ]
    }

@router.get("/search")
def search_documents(
    query: str,
    document_id: int | None = None,
    top_k: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty."
        )

    if top_k < 1 or top_k > 20:
        raise HTTPException(
            status_code=400,
            detail="top_k must be between 1 and 20."
        )

    results = semantic_search(
    query=query,
    db=db,
    document_id=document_id,
    top_k=top_k,
    user_id=cast(int, current_user.id)
    )

    # Record successful search activity
    activity = ActivityLog(
    user_id=current_user.id,
    activity_type="search"
    )

    db.add(activity)
    db.commit()

    return {
    "query": query,
    "result_count": len(results),
    "results": results
    }

@router.post("/ask")
def ask_question(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Validate conflicting document scopes if both are provided
        if request.document_id is not None and request.document_ids is not None:
            if set(request.document_ids) != {request.document_id}:
                raise HTTPException(
                    status_code=400,
                    detail="Conflicting document scopes: document_id and document_ids specify different documents."
                )

        effective_document_ids: list[int] | None = None
        if request.document_ids is not None:
            if len(request.document_ids) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Document selection cannot be empty."
                )
            effective_document_ids = list(dict.fromkeys(request.document_ids))
        elif request.document_id is not None:
            effective_document_ids = [request.document_id]

        # Verify that all requested documents exist and belong to the authenticated user
        if effective_document_ids is not None:
            owned_docs = (
                db.query(Document.id)
                .filter(
                    Document.user_id == current_user.id,
                    Document.id.in_(effective_document_ids)
                )
                .all()
            )
            owned_ids = {doc.id for doc in owned_docs}
            if len(owned_ids) != len(effective_document_ids):
                raise HTTPException(
                    status_code=404,
                    detail="One or more selected documents were not found."
                )

        conversation: Conversation | None = None
        if request.conversation_id is not None:
            conversation = (
                db.query(Conversation)
                .filter(
                    Conversation.id == request.conversation_id,
                    Conversation.user_id == current_user.id
                )
                .first()
            )
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found."
                )

        answer = answer_question(
            query=request.query,
            db=db,
            document_id=request.document_id,
            document_ids=effective_document_ids,
            top_k=request.top_k,
            user_id=cast(int, current_user.id)
        )

        # Persist conversation and messages on successful answer
        query_text = str(request.query).strip()
        if conversation is None:
            first_line = query_text.split("\n")[0].strip()
            title = (first_line[:47] + "...") if len(first_line) > 50 else first_line
            if not title:
                title = "New Conversation"

            scope_mode = "specific" if effective_document_ids is not None else "all"
            conversation = Conversation(
                user_id=current_user.id,
                title=title,
                scope_mode=scope_mode,
                selected_doc_ids=effective_document_ids
            )
            db.add(conversation)
            db.flush()
        else:
            conversation.scope_mode = "specific" if effective_document_ids is not None else "all"
            conversation.selected_doc_ids = effective_document_ids
            conversation.updated_at = func.now()

        user_message = ConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=query_text,
            sources=None
        )
        db.add(user_message)

        assistant_message = ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=answer.get("answer", ""),
            sources=answer.get("results", [])
        )
        db.add(assistant_message)
        db.flush()

        # Record successful AI question activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="ai_question"
        )

        db.add(activity)
        db.commit()

        answer["conversation_id"] = conversation.id
        answer["conversation_title"] = conversation.title
        answer["message_id"] = assistant_message.id

        return answer

    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )
    except (LLMServiceError, RuntimeError) as error:
        raise HTTPException(
            status_code=503,
            detail=str(error)
        )


@router.post("/suggested-questions", response_model=SuggestedQuestionsResponse)
def get_suggested_questions_endpoint(
    request: SuggestedQuestionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if request.document_ids is not None and len(request.document_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail="Document selection cannot be empty."
            )

        questions = get_document_suggested_questions(
            db=db,
            user_id=cast(int, current_user.id),
            document_ids=request.document_ids
        )

        return {
            "questions": questions,
            "scope": "specific" if request.document_ids is not None else "all"
        }
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate suggested questions: {error}"
        )


def _is_usable_summary(text: str | None) -> bool:
    """Validate that a summary is non-empty, usable, and not a fallback empty placeholder."""
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if stripped == "I couldn't generate a summary because the document is empty.":
        return False
    return True


def _generate_and_persist_summary(
    document: Document,
    summary_format: str,
    summary_length: str,
    db: Session,
    user_id: int
) -> str:
    """Safely generate a summary via LLM and persist it only on usable success."""
    if not document.extracted_text or not str(document.extracted_text).strip():
        raise HTTPException(
            status_code=400,
            detail="Original document text is unavailable or empty."
        )

    try:
        new_summary = generate_summary(
            str(document.extracted_text),
            summary_format=summary_format,
            summary_length=summary_length
        )
    except LLMConnectionError as error:
        raise HTTPException(
            status_code=503,
            detail=f"LLM connection error: {error}"
        )
    except LLMTimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail=f"LLM request timed out: {error}"
        )
    except (LLMServiceError, RuntimeError) as error:
        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    if not _is_usable_summary(new_summary):
        raise HTTPException(
            status_code=502,
            detail="Summary generation produced empty or unusable output."
        )

    setattr(document, "summary", new_summary)

    activity = ActivityLog(
        user_id=user_id,
        activity_type="summary"
    )

    db.add(activity)
    db.commit()
    db.refresh(document)

    return new_summary


@router.get("/{document_id}/summary")
def get_document_summary(
    document_id: int,
    format: str = "numbered",
    length: str = "detailed",
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    allowed_formats = {
        "numbered",
        "paragraphs",
        "bullets",
        "headings"
    }

    allowed_lengths = {"brief", "detailed"}

    if format not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail="Invalid summary format."
        )

    if length not in allowed_lengths:
        raise HTTPException(
            status_code=400,
            detail="Invalid summary length."
        )

    chunk_count = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).count()

    if regenerate or not _is_usable_summary(document.summary):
        summary = _generate_and_persist_summary(
            document=document,
            summary_format=format,
            summary_length=length,
            db=db,
            user_id=cast(int, current_user.id)
        )
        was_regenerated = True
    else:
        summary = str(document.summary)
        was_regenerated = False

    return {
        "document_id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "text_length": document.text_length,
        "chunk_count": chunk_count,
        "summary": summary,
        "summary_format": format,
        "summary_length": length,
        "regenerated": was_regenerated
    }


@router.post("/{document_id}/regenerate-summary")
def regenerate_document_summary(
    document_id: int,
    format: str = "numbered",
    length: str = "detailed",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_document_summary(
        document_id=document_id,
        format=format,
        length=length,
        regenerate=True,
        db=db,
        current_user=current_user
    )


@router.get("/{document_id}")
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = (
    db.query(Document)
    .filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    )
    .first()
)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    return {
        "id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "file_path": document.file_path,
        "text_length": document.text_length,
        "extracted_text": document.extracted_text,
        "created_at": document.created_at
    }

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    allowed_extensions = {".pdf", ".docx", ".txt"}

    # Validate filename
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is missing."
        )

    filename = Path(file.filename).name
    file_extension = Path(filename).suffix.lower()

    # Validate file type
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX, and TXT files are allowed."
        )

    # Save uploaded file
    file_path = UPLOAD_DIR / filename

    file_content = await file.read()

    with open(file_path, "wb") as buffer:
        buffer.write(file_content)

    # Process document
    try:
        processed_document = process_document(
            file_path,
            file_content
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    # Extract processed information
    extracted_text = processed_document["text"]
    chunks = processed_document["chunks"]
    embeddings = processed_document["embeddings"]

    
# Generate document summary
    summary = None
    summary_error = None

    try:
        raw_summary = generate_summary(extracted_text)
        if _is_usable_summary(raw_summary):
            summary = raw_summary
        else:
            summary = None
            summary_error = "Generated summary was empty or unusable."
    except Exception as error:
        summary_error = str(error)
        print(f"Summary generation failed: {error}")


    # Create document database record
    document = Document(
        filename=filename,
        document_type=file_extension.replace(".", "").upper(),
        file_path=str(file_path),
        extracted_text=extracted_text,
        text_length=len(extracted_text),
        summary=summary,
        user_id=current_user.id
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # Store document chunks and embeddings
    for index, chunk in enumerate(chunks):

        category = detect_chunk_category(chunk)

        document_chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            category=category,
            content=chunk,
            embedding=embeddings[index]
        )

        db.add(document_chunk)

    db.commit()

    # Record successful document upload activity
    activity = ActivityLog(
    user_id=current_user.id,
    activity_type="document_upload"
    )

    db.add(activity)
    db.commit()

    # Return upload result
    return {
        "message": "Document uploaded successfully!"
        if summary is not None
        else "Document uploaded successfully, but summary generation failed.",
        "document_id": document.id,
        "filename": filename,
        "size": len(file_content),
        "document_type": document.document_type,
        "text_length": len(extracted_text),
        "chunk_count": len(chunks),
        "summary": summary,
        "summary_status": (
            "success" if summary is not None else "failed"
        ),
        "summary_error": summary_error,
        "extracted_text": extracted_text
    }

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = (
    db.query(Document)
    .filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    )
    .first()
)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    file_path = Path(str(document.file_path))
    if file_path.exists():
        file_path.unlink()

    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).delete(synchronize_session=False)

    db.delete(document)
    db.commit()

    return {
        "message": "Document deleted successfully!",
        "document_id": document_id
    }