from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.cross_document_knowledge_graph import (
    CanonicalEntity,
    CrossDocumentEdge,
    CrossDocumentKnowledgeGraph,
    EntityOccurrence,
)

logger = logging.getLogger(__name__)


def get_cached_cross_document_graph(
    db: Session,
    *,
    user_id: int,
    collection_hash: str,
) -> Optional[CrossDocumentKnowledgeGraph]:
    """Retrieve existing cached cross-document graph matching collection_hash for the user."""
    return (
        db.query(CrossDocumentKnowledgeGraph)
        .filter(
            CrossDocumentKnowledgeGraph.user_id == user_id,
            CrossDocumentKnowledgeGraph.collection_hash == collection_hash,
        )
        .order_by(CrossDocumentKnowledgeGraph.id.desc())
        .first()
    )


def get_cross_document_graph_by_id(
    db: Session,
    *,
    graph_id: int,
    user_id: int,
) -> Optional[CrossDocumentKnowledgeGraph]:
    """Retrieve a cross-document graph by its ID, strictly scoped to user_id."""
    return (
        db.query(CrossDocumentKnowledgeGraph)
        .filter(
            CrossDocumentKnowledgeGraph.id == graph_id,
            CrossDocumentKnowledgeGraph.user_id == user_id,
        )
        .first()
    )


def delete_cross_document_graph(
    db: Session,
    *,
    graph_id: int,
    user_id: int,
) -> bool:
    """Explicitly delete a cross-document graph and all dependent entities, occurrences, and edges."""
    graph = get_cross_document_graph_by_id(db, graph_id=graph_id, user_id=user_id)
    if not graph:
        return False

    # Clean up dependent tables in SQL for robust SQLite compatibility
    db.query(EntityOccurrence).filter(EntityOccurrence.graph_id == graph.id).delete(synchronize_session=False)
    db.query(CrossDocumentEdge).filter(CrossDocumentEdge.graph_id == graph.id).delete(synchronize_session=False)
    db.query(CanonicalEntity).filter(CanonicalEntity.graph_id == graph.id).delete(synchronize_session=False)
    db.delete(graph)
    db.commit()
    return True


def replace_cross_document_graph(
    db: Session,
    *,
    user_id: int,
    collection_hash: str,
    selected_doc_ids: List[int],
    graph_version: str,
    generation_method: str,
    stats: Dict[str, Any],
    diagnostics: Dict[str, Any],
    entities_data: List[Dict[str, Any]],
    edges_data: List[Dict[str, Any]],
) -> CrossDocumentKnowledgeGraph:
    """Atomically create or replace a cross-document graph snapshot."""
    # Delete any existing graph matching this collection_hash for the user
    existing_graphs = (
        db.query(CrossDocumentKnowledgeGraph)
        .filter(
            CrossDocumentKnowledgeGraph.user_id == user_id,
            CrossDocumentKnowledgeGraph.collection_hash == collection_hash,
        )
        .all()
    )
    for eg in existing_graphs:
        db.query(EntityOccurrence).filter(EntityOccurrence.graph_id == eg.id).delete(synchronize_session=False)
        db.query(CrossDocumentEdge).filter(CrossDocumentEdge.graph_id == eg.id).delete(synchronize_session=False)
        db.query(CanonicalEntity).filter(CanonicalEntity.graph_id == eg.id).delete(synchronize_session=False)
        db.delete(eg)
    db.flush()

    new_graph = CrossDocumentKnowledgeGraph(
        user_id=user_id,
        collection_hash=collection_hash,
        selected_doc_ids_json=selected_doc_ids,
        graph_version=graph_version,
        status="ready",
        generation_method=generation_method,
        stats_json=stats,
        diagnostics_json=diagnostics,
    )
    db.add(new_graph)
    db.flush()

    # Create CanonicalEntity records and keep mapping entity_key -> CanonicalEntity
    entity_obj_map: Dict[str, CanonicalEntity] = {}
    for ent in entities_data:
        ce = CanonicalEntity(
            graph_id=new_graph.id,
            user_id=user_id,
            entity_key=ent["entity_key"],
            canonical_name=ent["canonical_name"],
            normalized_name=ent["normalized_name"],
            entity_type=ent.get("entity_type", "Concept"),
            description=ent.get("description"),
            aliases_json=ent.get("aliases", []),
            confidence=ent.get("confidence", 0.85),
            confidence_tier=ent.get("confidence_tier", "high"),
            importance_score=ent.get("importance_score", 0.5),
            document_count=ent.get("document_count", 1),
            occurrence_count=ent.get("occurrence_count", 1),
            is_shared=ent.get("is_shared", False),
            documents_json=ent.get("documents", []),
            metadata_json=ent.get("metadata", {}),
        )
        db.add(ce)
        db.flush()
        entity_obj_map[ent["entity_key"]] = ce

        # Add EntityOccurrence records
        for occ in ent.get("occurrences", []):
            eo = EntityOccurrence(
                canonical_entity_id=ce.id,
                graph_id=new_graph.id,
                user_id=user_id,
                document_id=occ["document_id"],
                document_name=occ.get("document_name", ""),
                chunk_id=occ.get("chunk_id"),
                page_number=occ.get("page_number", 1),
                original_label=occ.get("original_label", ent["canonical_name"]),
                source_text=occ.get("source_text", ""),
                resolution_confidence=occ.get("resolution_confidence", 0.90),
                resolution_method=occ.get("resolution_method", "exact_match"),
                evidence_json=occ.get("evidence", {}),
            )
            db.add(eo)

    # Create CrossDocumentEdge records
    for e in edges_data:
        src_obj = entity_obj_map.get(e["source_key"])
        tgt_obj = entity_obj_map.get(e["target_key"])
        if not src_obj or not tgt_obj:
            continue

        cde = CrossDocumentEdge(
            graph_id=new_graph.id,
            user_id=user_id,
            source_entity_id=src_obj.id,
            target_entity_id=tgt_obj.id,
            source_key=e["source_key"],
            target_key=e["target_key"],
            relationship=e["relationship"],
            origin=e.get("origin", "explicit"),
            confidence=e.get("confidence", 0.75),
            confidence_tier=e.get("confidence_tier", "high"),
            confidence_breakdown_json=e.get("confidence_breakdown", {}),
            evidence_count=e.get("evidence_count", 1),
            supporting_document_ids_json=e.get("supporting_document_ids", []),
            evidence_json=e.get("evidence", []),
            explanation=e.get("explanation"),
            is_cross_document=e.get("is_cross_document", False),
            metadata_json=e.get("metadata", {}),
        )
        db.add(cde)

    db.commit()
    db.refresh(new_graph)
    return new_graph

