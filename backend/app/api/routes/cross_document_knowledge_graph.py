from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.cross_document_knowledge_graph import (
    CanonicalEntityOut,
    CrossDocumentGraphDeleteResponse,
    CrossDocumentGraphGenerateRequest,
    CrossDocumentKnowledgeGraphResponse,
)
from app.services.cross_document_graph_service import (
    delete_cross_document_graph_endpoint,
    get_cross_document_graph_endpoint,
    get_or_generate_cross_document_graph,
)

router = APIRouter(prefix="/documents/knowledge-graph/cross-document", tags=["Cross-Document Knowledge Graph"])


@router.post("", response_model=CrossDocumentKnowledgeGraphResponse)
@router.post("/", response_model=CrossDocumentKnowledgeGraphResponse, include_in_schema=False)
def generate_or_get_cross_document_graph(
    payload: CrossDocumentGraphGenerateRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate or return cached cross-document knowledge graph across the user's selected documents.
    Strictly verifies user ownership of all selected documents.
    """
    if not payload.document_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one document ID in document_ids")

    return get_or_generate_cross_document_graph(
        db=db,
        user_id=current_user.id,
        document_ids=payload.document_ids,
        force_refresh=payload.force_refresh,
        include_low_confidence=payload.include_low_confidence,
        skip_llm=payload.skip_llm,
        max_nodes=payload.max_nodes,
        only_shared=payload.only_shared,
    )


@router.get("/{graph_id}", response_model=CrossDocumentKnowledgeGraphResponse)
def fetch_cross_document_graph_by_id(
    graph_id: int,
    include_low_confidence: bool = Query(default=False),
    only_shared: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch a stored cross-document knowledge graph by its ID.
    Strictly enforces current user ownership.
    """
    return get_cross_document_graph_endpoint(
        db=db,
        graph_id=graph_id,
        user_id=current_user.id,
        include_low_confidence=include_low_confidence,
        only_shared=only_shared,
    )


@router.get("/{graph_id}/entities", response_model=List[CanonicalEntityOut])
def list_cross_document_entities(
    graph_id: int,
    only_shared: bool = Query(default=False),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all or filtered canonical entities for a cross-document knowledge graph.
    Supports search query (?q=...) and shared-only filter (?only_shared=true).
    """
    graph_res = get_cross_document_graph_endpoint(
        db=db,
        graph_id=graph_id,
        user_id=current_user.id,
        include_low_confidence=True,
        only_shared=only_shared,
    )
    entities = graph_res.entities
    if q:
        query_norm = q.strip().lower()
        entities = [
            e for e in entities
            if query_norm in e.canonical_name.lower() or any(query_norm in a.lower() for a in e.aliases)
        ]
    return entities


@router.get("/{graph_id}/entity/{entity_key}", response_model=CanonicalEntityOut)
def get_cross_document_entity_detail(
    graph_id: int,
    entity_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information and occurrences for a single canonical entity.
    """
    graph_res = get_cross_document_graph_endpoint(
        db=db,
        graph_id=graph_id,
        user_id=current_user.id,
        include_low_confidence=True,
        only_shared=False,
    )
    for ent in graph_res.entities:
        if ent.entity_key == entity_key or str(ent.id) == entity_key:
            return ent
    raise HTTPException(status_code=404, detail="Entity not found in cross-document graph")


@router.get("/{graph_id}/evidence", response_model=List[Dict[str, Any]])
def get_cross_document_graph_evidence(
    graph_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all aggregated evidence items across edges and entities for this graph.
    """
    graph_res = get_cross_document_graph_endpoint(
        db=db,
        graph_id=graph_id,
        user_id=current_user.id,
        include_low_confidence=True,
        only_shared=False,
    )
    all_evidence = []
    for edge in graph_res.edges:
        for ev in edge.evidence:
            all_evidence.append({
                "type": "edge",
                "relationship": edge.relationship,
                "source": edge.source_key,
                "target": edge.target_key,
                **ev,
            })
    return all_evidence


@router.delete("/{graph_id}", response_model=CrossDocumentGraphDeleteResponse)
def remove_cross_document_graph(
    graph_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a stored cross-document knowledge graph.
    """
    deleted = delete_cross_document_graph_endpoint(
        db=db,
        graph_id=graph_id,
        user_id=current_user.id,
    )
    return CrossDocumentGraphDeleteResponse(
        graph_id=graph_id,
        deleted=deleted,
        message="Cross-document knowledge graph deleted successfully",
    )

