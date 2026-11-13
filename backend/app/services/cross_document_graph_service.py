from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.research_paper_analysis import ResearchPaperAnalysis
from app.models.cross_document_knowledge_graph import CrossDocumentKnowledgeGraph
from app.schemas.cross_document_knowledge_graph import (
    CROSS_DOCUMENT_GRAPH_VERSION,
    CanonicalEntityOut,
    CrossDocumentEdgeOut,
    CrossDocumentGraphStats,
    CrossDocumentKnowledgeGraphResponse,
    DocumentOccurrenceSummary,
    EntityOccurrenceOut,
    SelectedDocumentInfo,
)
from app.services.cross_document_entity_resolution import (
    ConceptCandidate,
    EntityResolutionPipeline,
    build_candidate_index,
    normalize_concept_label,
)
from app.services.cross_document_graph_repository import (
    delete_cross_document_graph as repo_delete_graph,
    get_cached_cross_document_graph,
    get_cross_document_graph_by_id,
    replace_cross_document_graph,
)
from app.services.knowledge_graph_evidence_service import assemble_substantive_document_units
from app.services.knowledge_graph_service import (
    _effective_content_hash,
    get_knowledge_graph,
    get_or_generate_knowledge_graph,
)

logger = logging.getLogger(__name__)


def compute_collection_hash(user_id: int, document_ids: List[int], doc_hashes: Dict[int, str]) -> str:
    """Compute deterministic cache key from user_id, sorted document_ids, and content hashes."""
    sorted_ids = sorted(list(set(document_ids)))
    hash_payload = f"{user_id}:{sorted_ids}:{[doc_hashes.get(d, '') for d in sorted_ids]}:{CROSS_DOCUMENT_GRAPH_VERSION}"
    return hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()


class UnionFind:
    """Disjoint Set Union structure for transitive concept unification."""

    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, i: int) -> int:
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: int, j: int) -> bool:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            if self.rank[root_i] < self.rank[root_j]:
                self.parent[root_i] = root_j
            elif self.rank[root_i] > self.rank[root_j]:
                self.parent[root_j] = root_i
            else:
                self.parent[root_j] = root_i
                self.rank[root_i] += 1
            return True
        return False


def get_or_generate_cross_document_graph(
    db: Session,
    *,
    user_id: int,
    document_ids: List[int],
    force_refresh: bool = False,
    include_low_confidence: bool = False,
    skip_llm: bool = True,
    max_nodes: int = 60,
    only_shared: bool = False,
) -> CrossDocumentKnowledgeGraphResponse:
    """
    Generate or return cached cross-document knowledge graph across the user's selected documents.
    Enforces strict user ownership, candidate pruning, multi-signal entity resolution, and grounded evidence.
    """
    t_start = time.perf_counter()
    unique_doc_ids = sorted(list(set(document_ids)))
    if not unique_doc_ids:
        raise HTTPException(status_code=400, detail="At least one document ID must be provided")

    # 1. Verify strict ownership of all requested documents
    docs = (
        db.query(Document)
        .filter(Document.id.in_(unique_doc_ids), Document.user_id == user_id)
        .all()
    )
    if len(docs) != len(unique_doc_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more selected documents do not exist or are not owned by the current user",
        )

    doc_map: Dict[int, Document] = {d.id: d for d in docs}
    doc_hashes: Dict[int, str] = {}
    for d in docs:
        try:
            _, _, _, _, base_h = assemble_substantive_document_units(d, db)
            doc_hashes[d.id] = _effective_content_hash(d, db, base_h)
        except Exception:
            doc_hashes[d.id] = str(getattr(d, "id", 0))

    # 2. Compute deterministic collection cache hash
    coll_hash = compute_collection_hash(user_id, unique_doc_ids, doc_hashes)

    # 3. Check cache
    if not force_refresh:
        cached_graph = get_cached_cross_document_graph(db, user_id=user_id, collection_hash=coll_hash)
        if cached_graph:
            return _format_graph_response(
                db=db,
                graph=cached_graph,
                doc_map=doc_map,
                cached=True,
                include_low_confidence=include_low_confidence,
                only_shared=only_shared,
            )

    # 4. Load or generate individual document graphs (reusing Phase 1)
    doc_graphs: Dict[int, Any] = {}
    for d_id in unique_doc_ids:
        doc_graph_res = get_or_generate_knowledge_graph(
            db=db,
            document_id=d_id,
            user_id=user_id,
            force_refresh=False,
            include_low_confidence=True,
            skip_llm=True,
            max_nodes=40,
        )
        doc_graphs[d_id] = doc_graph_res

    # 5. Build concept candidates
    candidates: List[ConceptCandidate] = []
    # Local node mapping: (doc_id, node_key) -> candidate index
    local_to_cand: Dict[Tuple[int, str], int] = {}

    for d_id in unique_doc_ids:
        g = doc_graphs[d_id]
        d_name = doc_map[d_id].filename or getattr(doc_map[d_id], "title", None) or f"Document #{d_id}"
        for node in g.nodes:
            cand_idx = len(candidates)
            norm_lbl = node.normalized_label or normalize_concept_label(node.label)
            excerpt_ctx = ""
            if node.evidence:
                excerpt_ctx = node.evidence[0].excerpt
            elif node.description:
                excerpt_ctx = node.description

            c = ConceptCandidate(
                document_id=d_id,
                document_name=d_name,
                node_key=node.node_key,
                label=node.label,
                normalized_label=norm_lbl,
                node_type=node.node_type,
                aliases=node.aliases or [],
                description=node.description,
                importance_score=node.importance_score,
                confidence=node.confidence,
                evidence=[ev.model_dump() for ev in node.evidence],
                source_pages=node.source_pages or [1],
                context_excerpt=excerpt_ctx,
            )
            candidates.append(c)
            local_to_cand[(d_id, node.node_key)] = cand_idx

    # 6. Candidate Pruning & Multi-Signal Entity Resolution
    pipeline = EntityResolutionPipeline(skip_llm=skip_llm)
    candidate_index = build_candidate_index(candidates)

    # Evaluate candidate pairs
    uf = UnionFind(len(candidates))
    evaluated_pairs: Set[Tuple[int, int]] = set()

    raw_candidate_pairs = 0
    filtered_candidate_pairs = 0
    verified_pairs = 0
    accepted_merges = 0
    rejected_merges = 0

    t_res_start = time.perf_counter()

    for key, indices in candidate_index.items():
        if len(indices) <= 1:
            continue
        # Check pairs of candidates that share this candidate key
        for i in range(len(indices)):
            idx_a = indices[i]
            for j in range(i + 1, len(indices)):
                idx_b = indices[j]
                cand_a = candidates[idx_a]
                cand_b = candidates[idx_b]

                # Only evaluate pairs across DIFFERENT documents
                if cand_a.document_id == cand_b.document_id:
                    continue

                pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                if pair in evaluated_pairs:
                    continue
                evaluated_pairs.add(pair)
                raw_candidate_pairs += 1

                decision = pipeline.evaluate_pair(cand_a, cand_b)
                filtered_candidate_pairs += 1

                if decision.same_entity and decision.confidence >= 0.75:
                    uf.union(idx_a, idx_b)
                    accepted_merges += 1
                    verified_pairs += 1
                else:
                    rejected_merges += 1

    t_res_end = time.perf_counter()

    # 7. Construct Canonical Entities from Clusters
    clusters: Dict[int, List[int]] = {}
    for idx in range(len(candidates)):
        root = uf.find(idx)
        clusters.setdefault(root, []).append(idx)

    entities_data: List[Dict[str, Any]] = []
    # Map candidate index -> entity_key
    cand_to_entity_key: Dict[int, str] = {}

    for root_idx, member_indices in clusters.items():
        member_cands = [candidates[i] for i in member_indices]

        # Determine canonical name: prefer longest descriptive label or highest importance
        sorted_by_desc = sorted(
            member_cands,
            key=lambda c: (len(c.label.split()), c.importance_score, len(c.label)),
            reverse=True,
        )
        canonical_name = sorted_by_desc[0].label
        norm_name = normalize_concept_label(canonical_name)
        entity_key = f"ent_{norm_name.replace(' ', '_')}"

        # Collect all aliases
        all_aliases = set()
        for mc in member_cands:
            all_aliases.add(mc.label)
            for a in mc.aliases:
                all_aliases.add(a)
        all_aliases.discard(canonical_name)

        # Entity type (majority vote)
        type_counts: Dict[str, int] = {}
        for mc in member_cands:
            type_counts[mc.node_type] = type_counts.get(mc.node_type, 0) + 1
        best_type = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[0][0]

        # Best description
        best_desc = next((mc.description for mc in member_cands if mc.description), None)

        # Build document breakdown & occurrences
        doc_grouped: Dict[int, List[ConceptCandidate]] = {}
        for mc in member_cands:
            doc_grouped.setdefault(mc.document_id, []).append(mc)

        doc_summaries: List[Dict[str, Any]] = []
        occurrences_list: List[Dict[str, Any]] = []

        for d_id, c_list in doc_grouped.items():
            d_name = doc_map[d_id].filename or getattr(doc_map[d_id], "title", None) or f"Document #{d_id}"
            pages: Set[int] = set()
            total_occ = 0
            for c in c_list:
                for p in c.source_pages:
                    pages.add(p)
                for ev in c.evidence:
                    total_occ += 1
                    occurrences_list.append({
                        "document_id": d_id,
                        "document_name": d_name,
                        "chunk_id": ev.get("chunk_id"),
                        "page_number": ev.get("page", 1),
                        "original_label": c.label,
                        "source_text": ev.get("excerpt", ""),
                        "resolution_confidence": c.confidence,
                        "resolution_method": "multi_signal_unified",
                        "evidence": ev,
                    })
            if total_occ == 0:
                # Fallback to at least one occurrence per candidate
                for c in c_list:
                    occurrences_list.append({
                        "document_id": d_id,
                        "document_name": d_name,
                        "chunk_id": None,
                        "page_number": c.source_pages[0] if c.source_pages else 1,
                        "original_label": c.label,
                        "source_text": c.context_excerpt or c.label,
                        "resolution_confidence": c.confidence,
                        "resolution_method": "document_concept",
                        "evidence": {"page": c.source_pages[0] if c.source_pages else 1, "excerpt": c.context_excerpt or c.label},
                    })
                total_occ = len(c_list)

            doc_summaries.append({
                "document_id": d_id,
                "document_name": d_name,
                "occurrences": total_occ,
                "source_pages": sorted(list(pages)) if pages else [1],
            })

        doc_count = len(doc_grouped)
        is_shared = doc_count >= 2
        conf = max(mc.confidence for mc in member_cands)
        if is_shared:
            conf = min(0.98, conf + 0.05)

        ent_dict = {
            "entity_key": entity_key,
            "canonical_name": canonical_name,
            "normalized_name": norm_name,
            "entity_type": best_type,
            "description": best_desc,
            "aliases": sorted(list(all_aliases)),
            "confidence": round(conf, 3),
            "confidence_tier": "high" if conf >= 0.75 else "medium",
            "importance_score": round(max(mc.importance_score for mc in member_cands), 3),
            "document_count": doc_count,
            "occurrence_count": len(occurrences_list),
            "is_shared": is_shared,
            "documents": doc_summaries,
            "occurrences": occurrences_list,
            "metadata": {"member_count": len(member_cands)},
        }
        entities_data.append(ent_dict)

        for member_idx in member_indices:
            cand_to_entity_key[member_idx] = entity_key

    # Sort entities by (is_shared desc, importance_score desc, occurrence_count desc)
    entities_data = sorted(
        entities_data,
        key=lambda e: (1 if e["is_shared"] else 0, e["importance_score"], e["occurrence_count"]),
        reverse=True,
    )
    if max_nodes and len(entities_data) > max_nodes:
        entities_data = entities_data[:max_nodes]

    retained_keys = {e["entity_key"] for e in entities_data}

    # 8. Cross-Document Grounded Relationships Aggregation
    edge_agg: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for d_id, g in doc_graphs.items():
        d_name = doc_map[d_id].filename or getattr(doc_map[d_id], "title", None) or f"Document #{d_id}"
        for e in g.edges:
            cand_src_idx = local_to_cand.get((d_id, e.source_key))
            cand_tgt_idx = local_to_cand.get((d_id, e.target_key))
            if cand_src_idx is None or cand_tgt_idx is None:
                continue

            src_key = cand_to_entity_key.get(cand_src_idx)
            tgt_key = cand_to_entity_key.get(cand_tgt_idx)
            if not src_key or not tgt_key:
                continue
            if src_key == tgt_key:
                continue  # Discard self-loops formed by alias merging
            if src_key not in retained_keys or tgt_key not in retained_keys:
                continue

            rel_key = (src_key, tgt_key, e.relationship)
            if rel_key not in edge_agg:
                edge_agg[rel_key] = {
                    "source_key": src_key,
                    "target_key": tgt_key,
                    "relationship": e.relationship,
                    "origin": e.origin,
                    "confidences": [e.confidence],
                    "supporting_document_ids": {d_id},
                    "evidence": [],
                    "explanations": [e.explanation] if e.explanation else [],
                }
            else:
                edge_agg[rel_key]["confidences"].append(e.confidence)
                edge_agg[rel_key]["supporting_document_ids"].add(d_id)
                if e.explanation:
                    edge_agg[rel_key]["explanations"].append(e.explanation)

            # Append evidence annotated with document metadata
            for ev in e.evidence:
                ev_dict = ev.model_dump()
                ev_dict["document_id"] = d_id
                ev_dict["document_name"] = d_name
                edge_agg[rel_key]["evidence"].append(ev_dict)

    edges_data: List[Dict[str, Any]] = []
    cross_doc_edge_count = 0

    for (s_k, t_k, rel), data in edge_agg.items():
        sup_docs = sorted(list(data["supporting_document_ids"]))
        is_cross = len(sup_docs) >= 2
        if is_cross:
            cross_doc_edge_count += 1

        base_conf = max(data["confidences"])
        if is_cross:
            base_conf = min(0.98, base_conf + 0.05 * (len(sup_docs) - 1))

        tier = "high" if base_conf >= 0.75 else ("medium" if base_conf >= 0.50 else "low")
        expl = " | ".join(data["explanations"]) if data["explanations"] else None

        edges_data.append({
            "source_key": s_k,
            "target_key": t_k,
            "relationship": rel,
            "origin": data["origin"],
            "confidence": round(base_conf, 3),
            "confidence_tier": tier,
            "confidence_breakdown": {
                "base_confidence": round(max(data["confidences"]), 3),
                "supporting_documents_count": len(sup_docs),
                "multi_doc_corroboration_score": 0.1 if is_cross else 0.0,
            },
            "evidence_count": len(data["evidence"]),
            "supporting_document_ids": sup_docs,
            "evidence": data["evidence"],
            "explanation": expl,
            "is_cross_document": is_cross,
        })

    # Sort edges: cross-document first, then confidence desc
    edges_data = sorted(
        edges_data,
        key=lambda e: (1 if e["is_cross_document"] else 0, e["confidence"], e["evidence_count"]),
        reverse=True,
    )

    t_end = time.perf_counter()
    gen_duration_ms = round((t_end - t_start) * 1000, 2)
    res_duration_ms = round((t_res_end - t_res_start) * 1000, 2)

    # 9. Compute Statistics & Diagnostics
    shared_ent_count = sum(1 for e in entities_data if e["is_shared"])
    doc_spec_count = len(entities_data) - shared_ent_count
    ent_type_counts: Dict[str, int] = {}
    for ent in entities_data:
        ent_type_counts[ent["entity_type"]] = ent_type_counts.get(ent["entity_type"], 0) + 1
    rel_counts: Dict[str, int] = {}
    for edge in edges_data:
        rel_counts[edge["relationship"]] = rel_counts.get(edge["relationship"], 0) + 1

    stats = {
        "total_entities": len(entities_data),
        "shared_entities": shared_ent_count,
        "document_specific_entities": doc_spec_count,
        "total_edges": len(edges_data),
        "cross_document_edges": cross_doc_edge_count,
        "documents_selected": len(unique_doc_ids),
        "entity_type_counts": ent_type_counts,
        "relationship_counts": rel_counts,
        "average_confidence": round(sum(e["confidence"] for e in edges_data) / len(edges_data), 3) if edges_data else 0.85,
        "grounded_edge_ratio": 1.0,
    }

    diagnostics = {
        "documents_selected": len(unique_doc_ids),
        "concepts_loaded": len(candidates),
        "raw_candidate_pairs": raw_candidate_pairs,
        "filtered_candidate_pairs": filtered_candidate_pairs,
        "verified_pairs": verified_pairs,
        "accepted_merges": accepted_merges,
        "rejected_merges": rejected_merges,
        "shared_entities": shared_ent_count,
        "document_specific_entities": doc_spec_count,
        "cross_document_edges": cross_doc_edge_count,
        "evidence_links": sum(len(e["evidence"]) for e in edges_data),
        "entity_resolution_latency_ms": res_duration_ms,
        "total_generation_latency_ms": gen_duration_ms,
        "cache_hit": False,
    }

    # 10. Persist atomically
    new_graph = replace_cross_document_graph(
        db=db,
        user_id=user_id,
        collection_hash=coll_hash,
        selected_doc_ids=unique_doc_ids,
        graph_version=CROSS_DOCUMENT_GRAPH_VERSION,
        generation_method="deterministic" if skip_llm else "hybrid",
        stats=stats,
        diagnostics=diagnostics,
        entities_data=entities_data,
        edges_data=edges_data,
    )

    return _format_graph_response(
        db=db,
        graph=new_graph,
        doc_map=doc_map,
        cached=False,
        include_low_confidence=include_low_confidence,
        only_shared=only_shared,
    )


def get_cross_document_graph_endpoint(
    db: Session,
    *,
    graph_id: int,
    user_id: int,
    include_low_confidence: bool = False,
    only_shared: bool = False,
) -> CrossDocumentKnowledgeGraphResponse:
    """Fetch an existing cross-document graph by its ID."""
    graph = get_cross_document_graph_by_id(db, graph_id=graph_id, user_id=user_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Cross-document knowledge graph not found")

    docs = (
        db.query(Document)
        .filter(Document.id.in_(graph.selected_doc_ids_json), Document.user_id == user_id)
        .all()
    )
    doc_map = {d.id: d for d in docs}
    return _format_graph_response(
        db=db,
        graph=graph,
        doc_map=doc_map,
        cached=True,
        include_low_confidence=include_low_confidence,
        only_shared=only_shared,
    )


def delete_cross_document_graph_endpoint(
    db: Session,
    *,
    graph_id: int,
    user_id: int,
) -> bool:
    """Delete a cross-document graph by its ID."""
    deleted = repo_delete_graph(db, graph_id=graph_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cross-document knowledge graph not found")
    return True


def _format_graph_response(
    db: Session,
    graph: CrossDocumentKnowledgeGraph,
    doc_map: Dict[int, Document],
    cached: bool,
    include_low_confidence: bool = False,
    only_shared: bool = False,
) -> CrossDocumentKnowledgeGraphResponse:
    """Format stored CrossDocumentKnowledgeGraph into response schema."""
    selected_docs_info: List[SelectedDocumentInfo] = []
    for d_id in (graph.selected_doc_ids_json or []):
        doc = doc_map.get(d_id)
        if doc:
            selected_docs_info.append(
                SelectedDocumentInfo(
                    document_id=doc.id,
                    title=getattr(doc, "title", None) or doc.filename or f"Doc #{doc.id}",
                    filename=doc.filename or "",
                    document_type=getattr(doc, "document_type", None) or getattr(doc, "file_type", "pdf"),
                    page_count=getattr(doc, "page_count", 1) or 1,
                    is_handwritten=bool(getattr(doc, "is_handwritten", False)),
                )
            )

    entities_out: List[CanonicalEntityOut] = []
    for ce in graph.canonical_entities:
        if only_shared and not ce.is_shared:
            continue

        occurrences_out = [
            EntityOccurrenceOut(
                id=occ.id,
                document_id=occ.document_id,
                document_name=occ.document_name,
                chunk_id=occ.chunk_id,
                page_number=occ.page_number,
                original_label=occ.original_label,
                source_text=occ.source_text,
                resolution_confidence=occ.resolution_confidence,
                resolution_method=occ.resolution_method,
                evidence=occ.evidence_json or {},
            )
            for occ in ce.occurrences
        ]

        doc_summaries = [
            DocumentOccurrenceSummary(
                document_id=ds["document_id"],
                document_name=ds.get("document_name", ""),
                occurrences=ds.get("occurrences", 1),
                source_pages=ds.get("source_pages", [1]),
            )
            for ds in (ce.documents_json or [])
        ]

        entities_out.append(
            CanonicalEntityOut(
                id=ce.id,
                entity_key=ce.entity_key,
                canonical_name=ce.canonical_name,
                normalized_name=ce.normalized_name,
                entity_type=ce.entity_type,
                description=ce.description,
                aliases=ce.aliases_json or [],
                confidence=ce.confidence,
                confidence_tier=ce.confidence_tier,
                importance_score=ce.importance_score,
                document_count=ce.document_count,
                occurrence_count=ce.occurrence_count,
                is_shared=ce.is_shared,
                documents=doc_summaries,
                occurrences=occurrences_out,
                metadata=ce.metadata_json or {},
            )
        )

    edges_out: List[CrossDocumentEdgeOut] = []
    visible_entity_keys = {e.entity_key for e in entities_out}

    for cde in graph.edges:
        if not include_low_confidence and cde.confidence_tier == "low":
            continue
        if cde.source_key not in visible_entity_keys or cde.target_key not in visible_entity_keys:
            continue

        edges_out.append(
            CrossDocumentEdgeOut(
                id=cde.id,
                source_key=cde.source_key,
                target_key=cde.target_key,
                relationship=cde.relationship,
                origin=cde.origin,
                confidence=cde.confidence,
                confidence_tier=cde.confidence_tier,
                confidence_breakdown=cde.confidence_breakdown_json or {},
                evidence_count=cde.evidence_count,
                supporting_document_ids=cde.supporting_document_ids_json or [],
                evidence=cde.evidence_json or [],
                explanation=cde.explanation,
                is_cross_document=cde.is_cross_document,
            )
        )

    stats = CrossDocumentGraphStats(**(graph.stats_json or {}))
    stats.total_entities = len(entities_out)
    stats.total_edges = len(edges_out)

    diag = dict(graph.diagnostics_json or {})
    diag["cache_hit"] = cached

    return CrossDocumentKnowledgeGraphResponse(
        id=graph.id,
        collection_hash=graph.collection_hash,
        selected_document_ids=graph.selected_doc_ids_json or [],
        selected_documents=selected_docs_info,
        graph_version=graph.graph_version,
        status=graph.status,
        generation_method=graph.generation_method,
        cached=cached,
        is_outdated=False,
        stats=stats,
        entities=entities_out,
        edges=edges_out,
        diagnostics=diag,
        created_at=graph.created_at,
        updated_at=graph.updated_at,
    )

