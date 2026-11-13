from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from app.schemas.knowledge_graph import (
    ALLOWED_RELATIONSHIPS,
    confidence_to_tier,
    normalize_relationship,
)
from app.services.embedding_services import generate_embedding
from app.services.handwriting.ollama_client import query_ollama_json
from app.services.knowledge_graph_evidence_service import (
    SentenceSpan,
    build_term_pattern,
    find_pair_evidence,
    sanitize_evidence_list,
)
from app.services.research.paper_section_service import ChunkUnit
from app.services.similarity_service import cosine_similarity


# Ordered from most specific directional technical/causal cues to general cues
_PATTERN_RULES: List[Tuple[re.Pattern, str, bool]] = [
    # Passive forms (swap=True means object precedes subject in surface clause)
    (re.compile(r"\bis\s+(?:exploited|abused|targeted)\s+by\b"), "depends_on", True),
    (re.compile(r"\b(?:is|are)\s+(?:mitigated|prevented|blocked)\s+by\b"), "contradicts", True),
    (re.compile(r"\b(?:is|are)\s+(?:caused|triggered|induced)\s+by\b"), "causes", True),
    (re.compile(r"\b(?:is|are)\s+(?:used|utilized|employed)\s+by\b"), "uses", True),
    (re.compile(r"\b(?:is|are)\s+(?:measured|assessed|quantified)\s+by\b"), "measured_by", False),
    (re.compile(r"\b(?:is|are)\s+(?:evaluated|tested|trained|benchmarked)\s+on\b"), "evaluated_on", False),
    (re.compile(r"\b(?:is|are)\s+defined\s+(?:as|by)\b"), "defined_by", False),
    (re.compile(r"\b(?:is|are)\s+compared\s+(?:with|to)\b"), "compared_with", False),
    # Active forms
    (re.compile(r"\b(?:exploits?|abuses?|targets?)\b"), "depends_on", False),
    (re.compile(r"\b(?:mitigates?|prevents?|defends?\s+against|protects?\s+against|blocks?)\b"), "contradicts", False),
    (re.compile(r"\b(?:exhausts?|consumes?|degrades?|disrupts?|overwhelms?|reduces?)\b"), "degrades", False),
    (re.compile(r"\b(?:causes?|triggers?|induces?)\b"), "causes", False),
    (re.compile(r"\b(?:leads?\s+to|results?\s+in|produces?|generates?)\b"), "results_in", False),
    (re.compile(r"\b(?:is\s+a|is\s+an|type\s+of|kind\s+of|example\s+of)\b"), "example_of", False),
    (re.compile(r"\b(?:defined\s+as|defined\s+by|refers\s+to)\b"), "defined_by", False),
    (re.compile(r"\b(?:contains?|includes?|consists?\s+of|comprises?)\b"), "contains", False),
    (re.compile(r"\b(?:part\s+of|stage\s+of|step\s+in|phase\s+of|belongs?\s+to)\b"), "part_of", False),
    (re.compile(r"\b(?:implements?|realizes?|encodes?)\b"), "implements", False),
    (re.compile(r"\b(?:extends?|builds?\s+on)\b"), "extends", False),
    (re.compile(r"\b(?:improves?|enhances?|outperforms?|solves?|addresses?)\b"), "improves", False),
    (re.compile(r"\b(?:depends?\s+on|relies?\s+on|requires?)\b"), "depends_on", False),
    (re.compile(r"\b(?:uses?|utilizes?|employs?|applies?|via)\b"), "uses", False),
    (re.compile(r"\b(?:supports?|validates?|confirms?)\b"), "supports", False),
    (re.compile(r"\b(?:contradicts?|conflicts?\s+with)\b"), "contradicts", False),
    (re.compile(r"\b(?:precedes?|before)\b"), "precedes", False),
    (re.compile(r"\b(?:follows?|after)\b"), "follows", False),
]


def _find_node_positions_in_sentence(
    sentence_lower: str,
    compiled_nodes: List[Tuple[str, List[re.Pattern]]],
) -> List[Tuple[str, int, int]]:
    hits: List[Tuple[str, int, int]] = []
    for node_key, patterns in compiled_nodes:
        best_span: Optional[Tuple[int, int]] = None
        for pat in patterns:
            m = pat.search(sentence_lower)
            if m:
                if best_span is None or (m.end() - m.start()) > (best_span[1] - best_span[0]):
                    best_span = (m.start(), m.end())
        if best_span is not None:
            hits.append((node_key, best_span[0], best_span[1]))
    hits.sort(key=lambda item: item[1])
    return hits


def _match_clause_relationship(clause: str) -> Optional[Tuple[str, bool]]:
    if not clause or len(clause) > 120:
        return None
    for pat, rel, swap in _PATTERN_RULES:
        if pat.search(clause):
            return rel, swap
    return None


def _compute_confidence(
    *,
    evidence_count: int,
    same_sentence_count: int,
    min_distance: int,
    origin: str,
    semantic_sim: float,
    llm_verified: bool,
) -> Tuple[float, Dict[str, float]]:
    ev_score = min(1.0, 0.50 + 0.16 * max(0, evidence_count - 1))
    if same_sentence_count > 0 or min_distance == 0:
        prox_score = 1.0
    elif min_distance <= 2:
        prox_score = 0.78
    else:
        prox_score = 0.45

    if origin == "explicit":
        exp_score = 0.95
    elif origin == "derived":
        exp_score = 0.68
    else:
        exp_score = 0.45

    sem_score = min(0.95, max(0.35, 0.52 + 0.42 * max(0.0, semantic_sim)))

    if llm_verified:
        llm_score = 0.92
    elif origin == "explicit":
        llm_score = 0.66
    elif min_distance <= 2:
        llm_score = 0.48
    else:
        llm_score = 0.28

    total = (
        0.24 * ev_score
        + 0.24 * prox_score
        + 0.24 * exp_score
        + 0.14 * sem_score
        + 0.14 * llm_score
    )
    return round(min(0.98, max(0.05, total)), 3), {
        "evidence_count_score": round(ev_score, 3),
        "proximity_score": round(prox_score, 3),
        "explicitness_score": round(exp_score, 3),
        "semantic_score": round(sem_score, 3),
        "llm_agreement_score": round(llm_score, 3),
    }


def _verify_candidates_with_ollama(
    candidates: List[Dict[str, Any]],
    node_map: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[Tuple[str, str], Dict[str, Any]], Dict[str, int]]:
    """
    Bounded Stage B LLM verification on already grounded Stage A candidate pairs.
    Sends at most 2 compact batches of <= 15 candidates each (`timeout=35s`).
    """
    verifications: Dict[Tuple[str, str], Dict[str, Any]] = {}
    metrics: Dict[str, Any] = {
        "llm_batches": 0,
        "llm_verified_count": 0,
        "llm_rejected_invalid_rel": 0,
        "llm_rejected_ungrounded": 0,
        "llm_fallback_used": 0,
        "llm_total_latency_ms": 0.0,
        "llm_max_latency_ms": 0.0,
    }

    system_prompt = (
        "You verify directed relationships between document concepts strictly from the given excerpt. "
        f"Allowed relationships ONLY: {', '.join(ALLOWED_RELATIONSHIPS)}, or NONE. "
        "Do NOT invent concepts. Do NOT add relationships not stated in the excerpt. "
        'Return strict JSON: {"relations": [{"source": "...", "target": "...", "relationship": "...", "reason": "..."}]}'
    )

    limited = candidates[:30]
    for start in range(0, len(limited), 15):
        batch = limited[start : start + 15]
        if not batch:
            continue
        metrics["llm_batches"] += 1

        prompt_items = []
        for idx, cand in enumerate(batch, 1):
            src_label = node_map[cand["source_key"]]["label"]
            tgt_label = node_map[cand["target_key"]]["label"]
            excerpt = cand["evidence"][0]["excerpt"] if cand["evidence"] else ""
            prompt_items.append(
                f"{idx}. Source: \"{src_label}\" | Target: \"{tgt_label}\" | Candidate: {cand['relationship']} | Excerpt: \"{excerpt}\""
            )

        user_prompt = (
            "Verify whether the excerpt directly supports a relationship between Source and Target "
            "(you may refine the relationship using the allowed vocabulary, reverse source/target if grammar clearly requires it, or return NONE if unsupported):\n\n"
            + "\n".join(prompt_items)
        )

        t_llm = time.perf_counter()
        try:
            raw = query_ollama_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                timeout=35,
                num_ctx=4096,
                num_predict=550,
            )
            lat_ms = round((time.perf_counter() - t_llm) * 1000, 2)
            metrics["llm_total_latency_ms"] = round(metrics["llm_total_latency_ms"] + lat_ms, 2)
            metrics["llm_max_latency_ms"] = max(metrics["llm_max_latency_ms"], lat_ms)

            if not raw or not isinstance(raw, dict):
                metrics["llm_fallback_used"] += 1
                continue

            label_to_key = {}
            for k, n in node_map.items():
                label_to_key[n["label"].lower()] = k
                for al in n.get("aliases", []):
                    label_to_key[al.lower()] = k

            for row in raw.get("relations") or []:
                if not isinstance(row, dict):
                    continue
                rel_raw = str(row.get("relationship") or "").strip()
                if rel_raw.upper() == "NONE":
                    continue
                normalized_rel = normalize_relationship(rel_raw)
                if not normalized_rel:
                    metrics["llm_rejected_invalid_rel"] += 1
                    continue

                src_key = label_to_key.get(str(row.get("source") or "").strip().lower())
                tgt_key = label_to_key.get(str(row.get("target") or "").strip().lower())
                if not src_key or not tgt_key or src_key == tgt_key:
                    metrics["llm_rejected_ungrounded"] += 1
                    continue

                verifications[(src_key, tgt_key)] = {
                    "relationship": normalized_rel,
                    "reason": str(row.get("reason") or "").strip()[:220],
                }
                metrics["llm_verified_count"] += 1
        except Exception:
            metrics["llm_fallback_used"] += 1

    return verifications, metrics


def build_grounded_relationships(
    *,
    nodes: Sequence[Dict[str, Any]],
    spans: Sequence[SentenceSpan],
    units: Sequence[ChunkUnit],
    used_research_analysis: bool = False,
    skip_llm: bool = False,
) -> Dict[str, Any]:
    """
    Stage A: Discover candidate edges deterministically from intra-sentence syntax cues,
    adjacent-sentence proximity, research structural links, and section co-occurrence.
    Stage B: Bounded Ollama verification with strict vocabulary + grounding validation.
    """
    if len(nodes) < 2:
        return {
            "edges": [],
            "generation_method": "deterministic",
            "diagnostics": {
                "candidate_pairs": 0,
                "raw_candidate_pairs": 0,
                "filtered_candidate_pairs": 0,
                "verified_pairs": 0,
                "accepted_edges": 0,
                "explicit_edges": 0,
                "derived_edges": 0,
                "rejected_self_loops": 0,
                "rejected_invalid_relationships": 0,
                "rejected_evidence_free": 0,
                "rejected_evidence_free_pairs": 0,
            },
        }

    node_map: Dict[str, Dict[str, Any]] = {n["node_key"]: n for n in nodes}
    valid_chunk_ids: Set[Optional[int]] = {u.chunk_id for u in units}
    max_page = max((int(u.page or 1) for u in units), default=1)

    compiled_nodes: List[Tuple[str, List[re.Pattern]]] = []
    node_embeddings: Dict[str, Optional[List[float]]] = {}
    for node in nodes:
        terms = [node["label"], *node.get("aliases", [])]
        compiled_nodes.append((node["node_key"], [build_term_pattern(t) for t in terms if (t or "").strip()]))
        try:
            node_embeddings[node["node_key"]] = generate_embedding(node["label"])
        except Exception:
            node_embeddings[node["node_key"]] = None

    # Track per-sentence entity occurrences
    sent_hits_map: List[List[Tuple[str, int, int]]] = []
    node_sent_indices: Dict[str, List[int]] = {n["node_key"]: [] for n in nodes}
    node_chunk_indices: Dict[str, Set[int]] = {n["node_key"]: set() for n in nodes}

    for sp in spans:
        hits = _find_node_positions_in_sentence(sp.lower_text, compiled_nodes)
        sent_hits_map.append(hits)
        seen_in_sent: Set[str] = set()
        for k, _, _ in hits:
            if k not in seen_in_sent:
                node_sent_indices[k].append(sp.index)
                node_chunk_indices[k].add(sp.chunk_index)
                seen_in_sent.add(k)

    # Candidate pairs keyed by unordered node pair for scoring priority, storing explicit directional rules
    raw_candidates: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    rejected_self_loops = 0
    rejected_invalid = 0
    rejected_evidence_free = 0

    def _register_candidate(src_key: str, rel: str, tgt_key: str, origin: str, explicit_hits: int = 1) -> None:
        nonlocal rejected_self_loops, rejected_invalid
        if src_key == tgt_key:
            rejected_self_loops += 1
            return
        norm_rel = normalize_relationship(rel)
        if not norm_rel:
            rejected_invalid += 1
            return
        k = (src_key, norm_rel, tgt_key)
        existing = raw_candidates.get(k)
        if existing is None:
            raw_candidates[k] = {
                "source_key": src_key,
                "target_key": tgt_key,
                "relationship": norm_rel,
                "origin": origin,
                "explicit_hits": explicit_hits,
            }
        else:
            existing["explicit_hits"] += explicit_hits
            if origin == "explicit":
                existing["origin"] = "explicit"

    # A1. Intra-sentence directional pattern extraction + same-sentence co-occurrence
    for sp, hits in zip(spans, sent_hits_map):
        if len(hits) < 2:
            continue
        # Only pair sequentially nearby mentions inside sentence to stay linear cleanly
        for i in range(len(hits)):
            k1, s1, e1 = hits[i]
            for j in range(i + 1, min(len(hits), i + 5)):
                k2, s2, e2 = hits[j]
                if k1 == k2:
                    continue
                between = sp.lower_text[e1:s2]
                matched = _match_clause_relationship(between)
                if matched:
                    rel, swap = matched
                    src, tgt = (k2, k1) if swap else (k1, k2)
                    _register_candidate(src, rel, tgt, "explicit", explicit_hits=1)
                elif (s2 - e1) <= 95:
                    _register_candidate(k1, "related_to", k2, "derived", explicit_hits=0)

    # A2. Adjacent-sentence & same-chunk co-occurrence (bounded neighborhood search)
    node_keys = [n["node_key"] for n in nodes]
    pair_co_scores: List[Tuple[float, str, str]] = []
    for i in range(len(node_keys)):
        k1 = node_keys[i]
        s_list1 = node_sent_indices[k1]
        c_set1 = node_chunk_indices[k1]
        if not s_list1 and not c_set1:
            continue
        for j in range(i + 1, len(node_keys)):
            k2 = node_keys[j]
            s_list2 = node_sent_indices[k2]
            c_set2 = node_chunk_indices[k2]
            shared_chunks = len(c_set1 & c_set2)
            if not shared_chunks:
                continue
            min_gap = 999
            for s1 in s_list1:
                for s2 in s_list2:
                    min_gap = min(min_gap, abs(s1 - s2))
            if min_gap <= 2 or shared_chunks >= 1:
                pair_score = (3.0 if min_gap == 0 else (2.0 if min_gap <= 2 else 0.7)) + 0.5 * shared_chunks
                pair_co_scores.append((pair_score, k1, k2))

    pair_co_scores.sort(reverse=True)
    for _, k1, k2 in pair_co_scores[:36]:
        # Only add fallback derived relation if no explicit directed edge between k1 and k2 yet
        has_explicit = any(
            (c["source_key"] == k1 and c["target_key"] == k2)
            or (c["source_key"] == k2 and c["target_key"] == k1)
            for c in raw_candidates.values()
            if c["origin"] == "explicit"
        )
        if not has_explicit:
            _register_candidate(k1, "related_to", k2, "derived", explicit_hits=0)

    # A3. Research-paper grounded structural edges (only if shared evidence exists!)
    if used_research_analysis:
        by_type: Dict[str, List[str]] = {}
        for n in nodes:
            by_type.setdefault(n["node_type"], []).append(n["node_key"])
        for meth in [*by_type.get("Method", []), *by_type.get("Model", [])][:4]:
            for prob in by_type.get("Problem", [])[:2]:
                _register_candidate(meth, "improves", prob, "derived", explicit_hits=0)
            for ds in by_type.get("Dataset", [])[:3]:
                _register_candidate(meth, "evaluated_on", ds, "derived", explicit_hits=0)
            for met in by_type.get("Metric", [])[:3]:
                _register_candidate(meth, "measured_by", met, "derived", explicit_hits=0)

    # Ground every candidate pair strictly to document spans BEFORE LLM verification
    grounded_candidates: List[Dict[str, Any]] = []
    for cand in raw_candidates.values():
        src_node = node_map[cand["source_key"]]
        tgt_node = node_map[cand["target_key"]]
        pair_ev = find_pair_evidence(
            [src_node["label"], *src_node.get("aliases", [])],
            [tgt_node["label"], *tgt_node.get("aliases", [])],
            spans,
            units,
            max_items=4,
            src_span_indices=node_sent_indices.get(cand["source_key"], []),
            tgt_span_indices=node_sent_indices.get(cand["target_key"], []),
        )
        cleaned_ev = sanitize_evidence_list(pair_ev["evidence"], valid_chunk_ids, max_page)
        if not cleaned_ev:
            rejected_evidence_free += 1
            continue

        grounded_candidates.append(
            {
                **cand,
                "evidence": cleaned_ev,
                "source_pages": pair_ev["source_pages"] or [ev["page"] for ev in cleaned_ev],
                "min_distance": pair_ev["min_distance"],
                "same_sentence_count": pair_ev["same_sentence_count"],
                "shared_chunk_count": pair_ev["shared_chunk_count"],
            }
        )

    # Rank candidates for bounded LLM Stage B verification (explicit & closest first)
    grounded_candidates.sort(
        key=lambda c: (
            0 if c["origin"] == "explicit" else 1,
            c["min_distance"],
            -len(c["evidence"]),
        )
    )

    llm_verifications: Dict[Tuple[str, str], Dict[str, Any]] = {}
    llm_metrics: Dict[str, int] = {
        "llm_batches": 0,
        "llm_verified_count": 0,
        "llm_rejected_invalid_rel": 0,
        "llm_rejected_ungrounded": 0,
        "llm_fallback_used": 0,
    }
    generation_method = "deterministic"

    if not skip_llm and grounded_candidates:
        llm_verifications, llm_metrics = _verify_candidates_with_ollama(grounded_candidates, node_map)
        if llm_metrics["llm_verified_count"] > 0:
            generation_method = "hybrid"

    # Merge Stage A + Stage B cleanly, compute transparent confidence, dedup, and filter
    final_edge_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for cand in grounded_candidates:
        sk, tk, rel = cand["source_key"], cand["target_key"], cand["relationship"]
        origin = cand["origin"]
        explanation: Optional[str] = None
        llm_verified = False

        if (sk, tk) in llm_verifications:
            rel = llm_verifications[(sk, tk)]["relationship"]
            explanation = llm_verifications[(sk, tk)].get("reason") or None
            llm_verified = True
        elif (tk, sk) in llm_verifications and origin != "explicit":
            # LLM detected natural direction reversal on derived pair
            sk, tk = tk, sk
            rel = llm_verifications[(sk, tk)]["relationship"]
            explanation = llm_verifications[(sk, tk)].get("reason") or None
            llm_verified = True

        if sk == tk:
            rejected_self_loops += 1
            continue

        rel_norm = normalize_relationship(rel)
        if not rel_norm:
            rejected_invalid += 1
            continue

        vec_s = node_embeddings.get(sk)
        vec_t = node_embeddings.get(tk)
        sem_sim = cosine_similarity(vec_s, vec_t) if (vec_s and vec_t) else 0.35

        conf, breakdown = _compute_confidence(
            evidence_count=len(cand["evidence"]),
            same_sentence_count=cand["same_sentence_count"],
            min_distance=cand["min_distance"],
            origin=origin,
            semantic_sim=sem_sim,
            llm_verified=llm_verified,
        )
        tier = confidence_to_tier(conf)

        edge_key = (sk, rel_norm, tk)
        prev = final_edge_map.get(edge_key)
        if prev is not None:
            if conf > prev["confidence"]:
                prev["confidence"] = conf
                prev["confidence_tier"] = tier
                prev["confidence_breakdown"] = breakdown
            continue

        if not explanation:
            src_lbl = node_map[sk]["label"]
            tgt_lbl = node_map[tk]["label"]
            explanation = f"{src_lbl} {rel_norm.replace('_', ' ')} {tgt_lbl} (page {', '.join(map(str, cand['source_pages'][:3]))})."

        final_edge_map[edge_key] = {
            "source_key": sk,
            "target_key": tk,
            "relationship": rel_norm,
            "origin": origin,
            "confidence": conf,
            "confidence_tier": tier,
            "confidence_breakdown": breakdown,
            "evidence_count": len(cand["evidence"]),
            "source_pages": sorted({int(p) for p in cand["source_pages"]}),
            "evidence": cand["evidence"],
            "explanation": explanation,
        }

    # Drop redundant generic `related_to` edges if a specific typed edge connects the same pair,
    # deduplicate undirected `related_to` pairs, and cap derived `related_to` edges for visual clarity.
    specific_pairs: Set[frozenset[str]] = {
        frozenset((e["source_key"], e["target_key"]))
        for e in final_edge_map.values()
        if e["relationship"] != "related_to"
    }
    typed_edges: List[Dict[str, Any]] = [
        edge for edge in final_edge_map.values() if edge["relationship"] != "related_to"
    ]
    seen_related_pairs: Set[frozenset[str]] = set()
    related_edges: List[Dict[str, Any]] = []
    for edge in sorted(
        (e for e in final_edge_map.values() if e["relationship"] == "related_to"),
        key=lambda e: (-e["confidence"], -e["evidence_count"]),
    ):
        pair_key = frozenset((edge["source_key"], edge["target_key"]))
        if pair_key in specific_pairs or pair_key in seen_related_pairs:
            continue
        seen_related_pairs.add(pair_key)
        related_edges.append(edge)

    max_related = max(14, len(nodes))
    edges: List[Dict[str, Any]] = [*typed_edges, *related_edges[:max_related]]
    edges.sort(key=lambda e: (-e["confidence"], -e["evidence_count"], e["source_key"], e["target_key"]))

    return {
        "edges": edges,
        "generation_method": generation_method,
        "diagnostics": {
            "candidate_pairs": len(grounded_candidates),
            "raw_candidate_pairs": len(raw_candidates),
            "filtered_candidate_pairs": len(raw_candidates) - rejected_self_loops - rejected_invalid,
            "verified_pairs": len(grounded_candidates),
            "accepted_edges": len(edges),
            "rejected_evidence_free_pairs": rejected_evidence_free,
            "rejected_self_loops": rejected_self_loops,
            "rejected_invalid_relationships": rejected_invalid + llm_metrics["llm_rejected_invalid_rel"],
            "rejected_evidence_free": rejected_evidence_free,
            **llm_metrics,
        },
    }
