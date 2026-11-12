from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge_graph import KnowledgeGraph
from app.models.research_paper_analysis import ResearchPaperAnalysis
from app.schemas.knowledge_graph import (
    GRAPH_VERSION,
    KnowledgeGraphResponse,
    KnowledgeGraphStats,
)
from app.services.knowledge_graph_evidence_service import (
    assemble_substantive_document_units,
    build_sentence_spans,
)
from app.services.knowledge_graph_extraction_service import extract_grounded_nodes
from app.services.knowledge_graph_relationship_service import build_grounded_relationships
from app.services.knowledge_graph_repository import (
    delete_knowledge_graph_by_document,
    get_cached_knowledge_graph,
    get_knowledge_graph_by_document,
    replace_knowledge_graph,
)


def _get_owned_document(db: Session, *, document_id: int, user_id: int) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _effective_content_hash(document: Document, db: Session, base_hash: str) -> str:
    """Include ResearchPaperAnalysis marker in cache key if present so graph enriches when analysis lands."""
    analysis = (
        db.query(ResearchPaperAnalysis)
        .filter(
            ResearchPaperAnalysis.document_id == document.id,
            ResearchPaperAnalysis.user_id == document.user_id,
        )
        .order_by(ResearchPaperAnalysis.id.desc())
        .first()
    )
    if analysis:
        return f"{base_hash}:rpa:{analysis.id}:{analysis.content_hash[:12]}"
    return base_hash


def _compute_stats(
    nodes: List[Dict[str, Any]],
    all_edges: List[Dict[str, Any]],
    visible_edges: List[Dict[str, Any]],
    *,
    used_research_analysis: bool,
    is_handwritten: bool,
) -> Dict[str, Any]:
    degree_map: Dict[str, int] = {n["node_key"]: 0 for n in nodes}
    rel_counts: Dict[str, int] = {}
    pages_covered = set()

    for n in nodes:
        for p in n.get("source_pages", []):
            pages_covered.add(int(p))

    explicit = 0
    derived = 0
    inferred = 0
    high = 0
    medium = 0
    low = 0
    grounded_edges = 0
    conf_sum = 0.0

    for e in visible_edges:
        degree_map[e["source_key"]] = degree_map.get(e["source_key"], 0) + 1
        degree_map[e["target_key"]] = degree_map.get(e["target_key"], 0) + 1
        rel_counts[e["relationship"]] = rel_counts.get(e["relationship"], 0) + 1
        if e["origin"] == "explicit":
            explicit += 1
        elif e["origin"] == "derived":
            derived += 1
        else:
            inferred += 1

        tier = e["confidence_tier"]
        if tier == "high":
            high += 1
        elif tier == "medium":
            medium += 1
        else:
            low += 1

        if e.get("evidence"):
            grounded_edges += 1
        conf_sum += float(e["confidence"])
        for p in e.get("source_pages", []):
            pages_covered.add(int(p))

    for n in nodes:
        n["degree"] = degree_map.get(n["node_key"], 0)

    node_type_counts: Dict[str, int] = {}
    grounded_nodes = 0
    for n in nodes:
        t = n["node_type"]
        node_type_counts[t] = node_type_counts.get(t, 0) + 1
        if n.get("evidence"):
            grounded_nodes += 1

    hidden_low = sum(1 for e in all_edges if e["confidence"] < 0.50) - sum(
        1 for e in visible_edges if e["confidence"] < 0.50
    )

    return KnowledgeGraphStats(
        node_count=len(nodes),
        edge_count=len(visible_edges),
        hidden_low_confidence_edges=max(0, hidden_low),
        explicit_edges=explicit,
        derived_edges=derived,
        inferred_edges=inferred,
        high_confidence_edges=high,
        medium_confidence_edges=medium,
        low_confidence_edges=low,
        average_edge_confidence=round(conf_sum / len(visible_edges), 3) if visible_edges else 0.0,
        grounded_edge_ratio=round(grounded_edges / len(visible_edges), 3) if visible_edges else 1.0,
        grounded_node_ratio=round(grounded_nodes / len(nodes), 3) if nodes else 1.0,
        node_type_counts=node_type_counts,
        relationship_counts=rel_counts,
        pages_covered=sorted(pages_covered),
        used_research_analysis=used_research_analysis,
        is_handwritten=is_handwritten,
    ).model_dump()


def _serialize_persisted_graph(
    graph: KnowledgeGraph,
    document: Document,
    *,
    cached: bool,
    is_outdated: bool,
    include_low_confidence: bool,
) -> KnowledgeGraphResponse:
    raw_nodes: List[Dict[str, Any]] = []
    for n in sorted(graph.nodes, key=lambda row: (-row.importance_score, -row.evidence_count, row.label)):
        raw_nodes.append(
            {
                "id": n.id,
                "node_key": n.node_key,
                "label": n.label,
                "normalized_label": n.normalized_label,
                "node_type": n.node_type,
                "description": n.description,
                "aliases": list(n.aliases_json or []),
                "confidence": round(float(n.confidence), 3),
                "confidence_tier": n.confidence_tier,
                "importance_score": round(float(n.importance_score), 3),
                "degree": 0,
                "evidence_count": int(n.evidence_count or 0),
                "source_pages": list(n.source_pages_json or []),
                "evidence": list(n.evidence_json or []),
                "metadata": dict(n.metadata_json or {}),
            }
        )

    all_edges: List[Dict[str, Any]] = []
    for e in sorted(graph.edges, key=lambda row: (-row.confidence, -row.evidence_count, row.source_key)):
        all_edges.append(
            {
                "id": e.id,
                "source_key": e.source_key,
                "target_key": e.target_key,
                "relationship": e.relationship,
                "origin": e.origin,
                "confidence": round(float(e.confidence), 3),
                "confidence_tier": e.confidence_tier,
                "confidence_breakdown": dict(e.confidence_breakdown_json or {}),
                "evidence_count": int(e.evidence_count or 0),
                "source_pages": list(e.source_pages_json or []),
                "evidence": list(e.evidence_json or []),
                "explanation": e.explanation,
            }
        )

    visible_edges = [
        e for e in all_edges if include_low_confidence or float(e["confidence"]) >= 0.50
    ]

    prior_stats = dict(graph.stats_json or {})
    stats = _compute_stats(
        raw_nodes,
        all_edges,
        visible_edges,
        used_research_analysis=bool(prior_stats.get("used_research_analysis", False)),
        is_handwritten=bool(document.is_handwritten),
    )

    return KnowledgeGraphResponse(
        document_id=document.id,
        filename=document.filename,
        document_type=document.document_type,
        is_handwritten=bool(document.is_handwritten),
        graph_version=graph.graph_version,
        content_hash=graph.content_hash,
        status=graph.status,
        generation_method=graph.generation_method,
        cached=cached,
        is_outdated=is_outdated,
        include_low_confidence=include_low_confidence,
        stats=stats,
        nodes=raw_nodes,
        edges=visible_edges,
        diagnostics=dict(graph.diagnostics_json or {}),
        created_at=graph.created_at,
        updated_at=graph.updated_at,
    )


def get_or_generate_knowledge_graph(
    *,
    db: Session,
    document_id: int,
    user_id: int,
    force_refresh: bool = False,
    include_low_confidence: bool = False,
    skip_llm: bool = False,
    max_nodes: int = 32,
) -> KnowledgeGraphResponse:
    """Generate (or retrieve valid cached) source-grounded Knowledge Graph for an owned document."""
    document = _get_owned_document(db, document_id=document_id, user_id=user_id)
    raw_units, substantive_units, section_hierarchy, pages_count, base_hash = (
        assemble_substantive_document_units(document, db)
    )
    effective_hash = _effective_content_hash(document, db, base_hash)

    if not force_refresh:
        cached_row = get_cached_knowledge_graph(
            db,
            document_id=document.id,
            user_id=user_id,
            content_hash=effective_hash,
            graph_version=GRAPH_VERSION,
        )
        if cached_row is not None:
            return _serialize_persisted_graph(
                cached_row,
                document,
                cached=True,
                is_outdated=False,
                include_low_confidence=include_low_confidence,
            )

    spans = build_sentence_spans(substantive_units)
    if not substantive_units or not spans:
        empty_stats = _compute_stats(
            [],
            [],
            [],
            used_research_analysis=False,
            is_handwritten=bool(document.is_handwritten),
        )
        persisted = replace_knowledge_graph(
            db,
            user_id=user_id,
            document_id=document.id,
            content_hash=effective_hash,
            graph_version=GRAPH_VERSION,
            status="empty",
            generation_method="deterministic",
            stats=empty_stats,
            diagnostics={"reason": "No substantive text units extracted", "pages_count": pages_count},
            nodes_payload=[],
            edges_payload=[],
        )
        return _serialize_persisted_graph(
            persisted,
            document,
            cached=False,
            is_outdated=False,
            include_low_confidence=include_low_confidence,
        )

    extraction = extract_grounded_nodes(
        document=document,
        db=db,
        units=substantive_units,
        spans=spans,
        section_hierarchy=section_hierarchy,
        max_nodes=max_nodes,
    )
    nodes = extraction["nodes"]
    used_research_analysis = extraction["used_research_analysis"]

    rel_result = build_grounded_relationships(
        nodes=nodes,
        spans=spans,
        units=substantive_units,
        used_research_analysis=used_research_analysis,
        skip_llm=skip_llm,
    )
    all_edges = rel_result["edges"]
    visible_edges = [
        e for e in all_edges if include_low_confidence or float(e["confidence"]) >= 0.50
    ]

    stats = _compute_stats(
        nodes,
        all_edges,
        visible_edges,
        used_research_analysis=used_research_analysis,
        is_handwritten=bool(document.is_handwritten),
    )
    diagnostics = {
        "raw_unit_count": len(raw_units),
        "substantive_unit_count": len(substantive_units),
        "sentence_span_count": len(spans),
        "pages_count": pages_count,
        **extraction["diagnostics"],
        **rel_result["diagnostics"],
    }

    persisted = replace_knowledge_graph(
        db,
        user_id=user_id,
        document_id=document.id,
        content_hash=effective_hash,
        graph_version=GRAPH_VERSION,
        status="ready" if nodes else "empty",
        generation_method=rel_result["generation_method"],
        stats=stats,
        diagnostics=diagnostics,
        nodes_payload=nodes,
        edges_payload=all_edges,
    )

    return _serialize_persisted_graph(
        persisted,
        document,
        cached=False,
        is_outdated=False,
        include_low_confidence=include_low_confidence,
    )


def get_knowledge_graph(
    *,
    db: Session,
    document_id: int,
    user_id: int,
    include_low_confidence: bool = False,
) -> KnowledgeGraphResponse:
    """Fetch existing cached Knowledge Graph for an owned document, reporting outdated status."""
    document = _get_owned_document(db, document_id=document_id, user_id=user_id)
    graph = get_knowledge_graph_by_document(db, document_id=document.id, user_id=user_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Knowledge graph not found for this document")

    _, _, _, _, base_hash = assemble_substantive_document_units(document, db)
    current_hash = _effective_content_hash(document, db, base_hash)
    is_outdated = (graph.content_hash != current_hash) or (graph.graph_version != GRAPH_VERSION)

    return _serialize_persisted_graph(
        graph,
        document,
        cached=True,
        is_outdated=is_outdated,
        include_low_confidence=include_low_confidence,
    )


def delete_knowledge_graph(
    *,
    db: Session,
    document_id: int,
    user_id: int,
) -> bool:
    """Delete persisted knowledge graph after verifying document ownership."""
    _get_owned_document(db, document_id=document_id, user_id=user_id)
    return delete_knowledge_graph_by_document(db, document_id=document_id, user_id=user_id)

