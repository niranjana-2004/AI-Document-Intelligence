from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.knowledge_graph import (
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
)
from app.schemas.knowledge_graph import GRAPH_VERSION


def get_knowledge_graph_by_document(
    db: Session,
    *,
    document_id: int,
    user_id: int,
) -> Optional[KnowledgeGraph]:
    """Return the persisted knowledge graph row owned by `user_id` for `document_id`."""
    return (
        db.query(KnowledgeGraph)
        .filter(
            KnowledgeGraph.document_id == document_id,
            KnowledgeGraph.user_id == user_id,
        )
        .order_by(KnowledgeGraph.id.desc())
        .first()
    )


def get_cached_knowledge_graph(
    db: Session,
    *,
    document_id: int,
    user_id: int,
    content_hash: str,
    graph_version: str = GRAPH_VERSION,
) -> Optional[KnowledgeGraph]:
    """Return an up-to-date cached KnowledgeGraph matching `content_hash` and `graph_version`."""
    return (
        db.query(KnowledgeGraph)
        .filter(
            KnowledgeGraph.document_id == document_id,
            KnowledgeGraph.user_id == user_id,
            KnowledgeGraph.content_hash == content_hash,
            KnowledgeGraph.graph_version == graph_version,
        )
        .order_by(KnowledgeGraph.id.desc())
        .first()
    )


def delete_knowledge_graph_by_document(
    db: Session,
    *,
    document_id: int,
    user_id: int,
) -> bool:
    """Delete all stored knowledge graph rows/nodes/edges for `(user_id, document_id)`."""
    graphs = (
        db.query(KnowledgeGraph)
        .filter(
            KnowledgeGraph.document_id == document_id,
            KnowledgeGraph.user_id == user_id,
        )
        .all()
    )
    if not graphs:
        return False

    graph_ids = [g.id for g in graphs]
    db.query(KnowledgeGraphEdge).filter(KnowledgeGraphEdge.graph_id.in_(graph_ids)).delete(
        synchronize_session=False
    )
    db.query(KnowledgeGraphNode).filter(KnowledgeGraphNode.graph_id.in_(graph_ids)).delete(
        synchronize_session=False
    )
    db.query(KnowledgeGraph).filter(KnowledgeGraph.id.in_(graph_ids)).delete(
        synchronize_session=False
    )
    db.commit()
    return True


def replace_knowledge_graph(
    db: Session,
    *,
    user_id: int,
    document_id: int,
    content_hash: str,
    graph_version: str,
    status: str,
    generation_method: str,
    stats: Dict[str, Any],
    diagnostics: Dict[str, Any],
    nodes_payload: List[Dict[str, Any]],
    edges_payload: List[Dict[str, Any]],
) -> KnowledgeGraph:
    """Atomically replace any previous graph snapshot for `(user_id, document_id)`."""
    existing = (
        db.query(KnowledgeGraph)
        .filter(
            KnowledgeGraph.document_id == document_id,
            KnowledgeGraph.user_id == user_id,
        )
        .all()
    )
    if existing:
        existing_ids = [g.id for g in existing]
        db.query(KnowledgeGraphEdge).filter(KnowledgeGraphEdge.graph_id.in_(existing_ids)).delete(
            synchronize_session=False
        )
        db.query(KnowledgeGraphNode).filter(KnowledgeGraphNode.graph_id.in_(existing_ids)).delete(
            synchronize_session=False
        )
        for old_g in existing:
            db.delete(old_g)
        db.flush()

    now = datetime.now(timezone.utc)
    graph = KnowledgeGraph(
        user_id=user_id,
        document_id=document_id,
        content_hash=content_hash,
        graph_version=graph_version,
        status=status,
        generation_method=generation_method,
        stats_json=stats,
        diagnostics_json=diagnostics,
        created_at=now,
        updated_at=now,
    )
    db.add(graph)
    db.flush()

    node_key_to_id: Dict[str, int] = {}
    for item in nodes_payload:
        node = KnowledgeGraphNode(
            graph_id=graph.id,
            document_id=document_id,
            user_id=user_id,
            node_key=item["node_key"],
            label=item["label"],
            normalized_label=item["normalized_label"],
            node_type=item["node_type"],
            description=item.get("description"),
            aliases_json=item.get("aliases", []),
            confidence=float(item.get("confidence", 0.75)),
            confidence_tier=item.get("confidence_tier", "high"),
            importance_score=float(item.get("importance_score", 0.5)),
            evidence_count=int(item.get("evidence_count", 0)),
            source_pages_json=item.get("source_pages", []),
            evidence_json=item.get("evidence", []),
            metadata_json=item.get("metadata", {}),
        )
        db.add(node)
        db.flush()
        node_key_to_id[node.node_key] = node.id

    for edge_item in edges_payload:
        src_id = node_key_to_id.get(edge_item["source_key"])
        tgt_id = node_key_to_id.get(edge_item["target_key"])
        if src_id is None or tgt_id is None or src_id == tgt_id:
            continue
        edge = KnowledgeGraphEdge(
            graph_id=graph.id,
            document_id=document_id,
            user_id=user_id,
            source_node_id=src_id,
            target_node_id=tgt_id,
            source_key=edge_item["source_key"],
            target_key=edge_item["target_key"],
            relationship=edge_item["relationship"],
            origin=edge_item.get("origin", "explicit"),
            confidence=float(edge_item.get("confidence", 0.75)),
            confidence_tier=edge_item.get("confidence_tier", "high"),
            confidence_breakdown_json=edge_item.get("confidence_breakdown", {}),
            evidence_count=int(edge_item.get("evidence_count", 1)),
            source_pages_json=edge_item.get("source_pages", []),
            evidence_json=edge_item.get("evidence", []),
            explanation=edge_item.get("explanation"),
            metadata_json=edge_item.get("metadata", {}),
        )
        db.add(edge)

    db.commit()
    db.refresh(graph)
    return graph

