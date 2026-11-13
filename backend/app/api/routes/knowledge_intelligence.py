from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.knowledge_intelligence_cache import KnowledgeIntelligenceCache
from app.models.user import User
from app.schemas.knowledge_intelligence import (
    KnowledgeIntelligenceQueryRequest,
    KnowledgeIntelligenceResponse,
)
from app.services.knowledge_intelligence_service import (
    execute_knowledge_intelligence_query,
)

router = APIRouter(prefix="/documents/knowledge-intelligence", tags=["Knowledge Intelligence"])


@router.post("/query", response_model=KnowledgeIntelligenceResponse)
@router.post("/query/", response_model=KnowledgeIntelligenceResponse, include_in_schema=False)
def query_knowledge_intelligence(
    payload: KnowledgeIntelligenceQueryRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute a structured, source-grounded Knowledge Intelligence query across selected documents.
    Strictly verifies user ownership and tenant isolation.
    """
    return execute_knowledge_intelligence_query(
        db=db,
        user_id=current_user.id,
        request=payload,
    )


@router.get("/entity/{entity_key}", response_model=KnowledgeIntelligenceResponse)
def get_entity_intelligence_drilldown(
    entity_key: str,
    document_ids: Optional[str] = Query(default=None, description="Comma-separated document IDs"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Drill down on a specific entity across the user's selected documents.
    """
    doc_id_list: List[int] = []
    if document_ids:
        try:
            doc_id_list = [int(d.strip()) for d in document_ids.split(",") if d.strip().isdigit()]
        except Exception:
            doc_id_list = []

    entity_name = entity_key.split(":")[-1].replace("_", " ").title()
    req = KnowledgeIntelligenceQueryRequest(
        query=f"Explain everything Cognidocs knows about {entity_name}",
        document_ids=doc_id_list,
        focus_entity=entity_name,
        force_refresh=False,
    )
    return execute_knowledge_intelligence_query(
        db=db,
        user_id=current_user.id,
        request=req,
    )


@router.delete("/cache")
def clear_user_knowledge_cache(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Clear all cached Knowledge Intelligence query responses for the current user.
    """
    deleted_count = (
        db.query(KnowledgeIntelligenceCache)
        .filter(KnowledgeIntelligenceCache.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {
        "status": "success",
        "deleted_cache_entries": deleted_count,
        "message": f"Successfully cleared {deleted_count} cached knowledge intelligence queries.",
    }

