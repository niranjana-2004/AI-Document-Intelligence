from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.knowledge_graph import (
    KnowledgeGraphDeleteResponse,
    KnowledgeGraphGenerateRequest,
    KnowledgeGraphResponse,
)
from app.services.knowledge_graph_service import (
    delete_knowledge_graph,
    get_knowledge_graph,
    get_or_generate_knowledge_graph,
)


router = APIRouter(prefix="/documents", tags=["Knowledge Graph"])


@router.post("/{document_id}/knowledge-graph", response_model=KnowledgeGraphResponse)
def generate_document_knowledge_graph(
    document_id: int,
    payload: Optional[KnowledgeGraphGenerateRequest] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opts = payload or KnowledgeGraphGenerateRequest()
    return get_or_generate_knowledge_graph(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        force_refresh=opts.force_refresh,
        include_low_confidence=opts.include_low_confidence,
        skip_llm=opts.skip_llm,
        max_nodes=opts.max_nodes,
    )


@router.get("/{document_id}/knowledge-graph", response_model=KnowledgeGraphResponse)
def fetch_document_knowledge_graph(
    document_id: int,
    include_low_confidence: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_knowledge_graph(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        include_low_confidence=include_low_confidence,
    )


@router.delete("/{document_id}/knowledge-graph", response_model=KnowledgeGraphDeleteResponse)
def remove_document_knowledge_graph(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = delete_knowledge_graph(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )
    return KnowledgeGraphDeleteResponse(
        document_id=document_id,
        deleted=deleted,
        message="Knowledge graph deleted" if deleted else "No stored knowledge graph to delete",
    )


@router.post("/{document_id}/knowledge-graph/regenerate", response_model=KnowledgeGraphResponse)
def regenerate_document_knowledge_graph(
    document_id: int,
    payload: Optional[KnowledgeGraphGenerateRequest] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opts = payload or KnowledgeGraphGenerateRequest(force_refresh=True)
    return get_or_generate_knowledge_graph(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        force_refresh=True,
        include_low_confidence=opts.include_low_confidence,
        skip_llm=opts.skip_llm,
        max_nodes=opts.max_nodes,
    )

