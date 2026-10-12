import logging
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.conversation import Conversation, ConversationMessage
from app.schemas.conversation import (
    ConversationSummaryResponse,
    ConversationDetailResponse,
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ConversationMessageResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"]
)


@router.get("", response_model=list[ConversationSummaryResponse])
@router.get("/", response_model=list[ConversationSummaryResponse], include_in_schema=False)
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all conversations owned by the authenticated user, ordered by most recently updated.
    """
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    results = []
    for conv in conversations:
        msgs = conv.messages
        msg_count = len(msgs)
        last_preview = msgs[-1].content[:120].strip() if msg_count > 0 else None
        results.append(
            ConversationSummaryResponse(
                id=conv.id,
                title=conv.title,
                scope_mode=conv.scope_mode,
                selected_doc_ids=conv.selected_doc_ids,
                message_count=msg_count,
                last_message_preview=last_preview,
                created_at=conv.created_at,
                updated_at=conv.updated_at
            )
        )

    return results


@router.post("", response_model=ConversationDetailResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ConversationDetailResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_conversation(
    request: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Explicitly create a new conversation for the authenticated user.
    """
    selected_doc_ids = request.selected_doc_ids
    if request.scope_mode == "specific" and selected_doc_ids:
        # Validate that all selected documents belong to current_user
        unique_ids = list(dict.fromkeys(selected_doc_ids))
        owned_count = (
            db.query(Document.id)
            .filter(
                Document.user_id == current_user.id,
                Document.id.in_(unique_ids)
            )
            .count()
        )
        if owned_count != len(unique_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more selected documents are invalid or not owned by you."
            )
        selected_doc_ids = unique_ids

    title = request.title or "New Conversation"

    conversation = Conversation(
        user_id=current_user.id,
        title=title,
        scope_mode=request.scope_mode,
        selected_doc_ids=selected_doc_ids
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        scope_mode=conversation.scope_mode,
        selected_doc_ids=conversation.selected_doc_ids,
        messages=[],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve full conversation history, citations, and scope for a conversation
    owned by the authenticated user.
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found."
        )

    # Format messages
    ordered_messages = sorted(conversation.messages, key=lambda m: m.created_at)
    formatted_messages = [
        ConversationMessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            sources=m.sources,
            created_at=m.created_at
        )
        for m in ordered_messages
    ]

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        scope_mode=conversation.scope_mode,
        selected_doc_ids=conversation.selected_doc_ids,
        messages=formatted_messages,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.patch("/{conversation_id}", response_model=ConversationDetailResponse)
def update_conversation(
    conversation_id: int,
    request: ConversationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a conversation's title and/or document scope.
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found."
        )

    if request.title is not None:
        conversation.title = request.title

    if request.scope_mode is not None:
        conversation.scope_mode = request.scope_mode

    if request.selected_doc_ids is not None:
        if conversation.scope_mode == "specific" and request.selected_doc_ids:
            unique_ids = list(dict.fromkeys(request.selected_doc_ids))
            owned_count = (
                db.query(Document.id)
                .filter(
                    Document.user_id == current_user.id,
                    Document.id.in_(unique_ids)
                )
                .count()
            )
            if owned_count != len(unique_ids):
                raise HTTPException(
                    status_code=400,
                    detail="One or more selected documents are invalid or not owned by you."
                )
            conversation.selected_doc_ids = unique_ids
        else:
            conversation.selected_doc_ids = request.selected_doc_ids

    conversation.updated_at = func.now()

    db.commit()
    db.refresh(conversation)

    ordered_messages = sorted(conversation.messages, key=lambda m: m.created_at)
    formatted_messages = [
        ConversationMessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            sources=m.sources,
            created_at=m.created_at
        )
        for m in ordered_messages
    ]

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        scope_mode=conversation.scope_mode,
        selected_doc_ids=conversation.selected_doc_ids,
        messages=formatted_messages,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation and cascade-delete its messages.
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found."
        )

    db.delete(conversation)
    db.commit()

    return {
        "message": "Conversation deleted successfully.",
        "id": conversation_id
    }
