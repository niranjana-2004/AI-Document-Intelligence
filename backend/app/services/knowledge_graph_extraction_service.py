from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.handwritten_analysis import HandwrittenConcept
from app.models.research_paper_analysis import ResearchPaperAnalysis
from app.services.document_mind_map_service import (
    extract_standard_concepts_fallback,
    normalize_concept_label,
)
from app.services.embedding_services import generate_embedding
from app.services.knowledge_graph_evidence_service import (
    SentenceSpan,
    build_sentence_inverted_index,
    build_term_pattern,
    find_entity_evidence,
    sanitize_evidence_list,
)
from app.services.research.paper_section_service import ChunkUnit
from app.services.similarity_service import cosine_similarity


GENERIC_FILLER_LABELS: Set[str] = {
    "information",
    "system",
    "systems",
    "process",
    "processes",
    "data",
    "technology",
    "technologies",
    "thing",
    "things",
    "area",
    "areas",
    "study",
    "studies",
    "method",
    "methods",
    "approach",
    "approaches",
    "model",
    "models",
    "result",
    "results",
    "paper",
    "document",
    "documents",
    "section",
    "sections",
    "example",
    "examples",
    "number",
    "numbers",
    "way",
    "ways",
    "time",
    "work",
    "works",
    "part",
    "parts",
    "type",
    "types",
    "form",
    "forms",
    "case",
    "cases",
    "value",
    "values",
    "item",
    "items",
    "aspect",
    "aspects",
    "overview",
    "summary",
    "introduction",
    "conclusion",
    "abstract",
    "references",
    "acknowledgments",
    "appendix",
    "figure",
    "table",
    "page",
    "pages",
    "author",
    "authors",
    "notes",
    "note",
    "list",
    "set",
    "step",
    "steps",
    "issue",
    "issues",
    "problem",
    "solution",
    "impact",
    "feature",
    "features",
    "detail",
    "details",
    "point",
    "points",
    "content",
    "text",
    "output",
    "input",
    "analysis",
    "research",
    "user",
    "users",
    "it",
    "its",
    "how",
    "because",
    "if",
    "when",
    "where",
    "which",
    "what",
    "who",
    "whom",
    "whose",
    "why",
    "this",
    "that",
    "these",
    "those",
    "there",
    "then",
    "thus",
    "hence",
    "therefore",
    "although",
    "while",
    "after",
    "before",
    "also",
    "however",
    "furthermore",
    "moreover",
    "meanwhile",
    "news",
    "take",
    "takes",
    "each",
    "every",
    "some",
    "many",
    "such",
    "other",
    "others",
    "one",
    "two",
    "first",
    "second",
    "third",
    "members",
    "hood",
    "much",
}

NOISE_TOKENS: Set[str] = {
    "notes on",
    "page",
    "chapter",
    "how the attack works",
    "how it works",
    "key takeaways",
    "summary",
    "references",
    "future work",
    "limitations",
    "khenianca",
    "venice vocabulary",
}

_ACRONYM_DEF_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9\-/]{2,}(?:\s+[A-Za-z0-9\-/]{2,}){0,4})\s*\(([A-Z][A-Z0-9\-]{1,10})\)"
)
_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+|(?:\d+(?:\.\d+)*|[IVX]+)\.\s+)(.{3,75})$",
    re.MULTILINE,
)
_CAP_PHRASE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9\-]{1,}(?:\s+(?:of|for|on|in|to|with)?\s*[A-Z][A-Za-z0-9\-]{1,}){0,4})\b"
)
_DEF_SUBJECT_RE = re.compile(
    r"(?:^|[.!?]\s+)([A-Z][A-Za-z0-9\-/ ]{2,45}?)\s+(?:is\s+(?:a|an|the)|refers\s+to|means|represents)\s+",
    re.MULTILINE,
)
_TECH_ACRONYM_RE = re.compile(r"\b([A-Z][A-Z0-9\-]{1,9})\b")

_ACRONYM_STOPWORDS = {
    "THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT", "INTO", "WHEN",
    "WHAT", "HOW", "WHY", "ARE", "WAS", "NOT", "BUT", "CAN", "ALL", "NEW",
    "PAGE", "PDF", "DOCX", "TXT", "FIG", "TABLE", "SECTION", "PART", "NOTE",
    "NOTES", "STEP", "ONE", "TWO", "THREE", "FOUR", "FIVE", "USA", "MIN",
}


def _clean_candidate_label(raw: str) -> str:
    cleaned = re.sub(r"^[\d\.\)\-\*#:\s]+", "", (raw or "").strip())
    cleaned = re.sub(r"[:;,\.\s]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Strip trailing parenthetical if we handle acronyms separately
    cleaned = re.sub(r"\s*\([^)]{1,18}\)\s*$", "", cleaned).strip()
    return cleaned


def _canonical_dedup_key(label: str) -> str:
    norm = normalize_concept_label(label)
    if norm.endswith("s") and len(norm) > 5 and not norm.endswith(("ss", "us", "is", "os")):
        singular = norm[:-1]
        if singular:
            return singular
    return norm


def _is_generic_or_noisy(label: str) -> bool:
    if not label or len(label) < 2 or len(label) > 85:
        return True
    lowered = label.lower().strip()
    if lowered in GENERIC_FILLER_LABELS:
        return True
    if any(noise in lowered for noise in NOISE_TOKENS):
        return True
    words = lowered.split()
    if len(words) > 7:
        return True
    if words and words[0] in {"the", "a", "an", "each", "every", "some", "many", "any", "it", "how", "because", "if", "this", "that"}:
        trimmed = " ".join(words[1:])
        if not trimmed or trimmed in GENERIC_FILLER_LABELS or len(words) <= 2:
            return True
    alpha_count = sum(1 for c in label if c.isalpha())
    if alpha_count < 2:
        return True
    if any(ch in label for ch in ("http://", "https://", "www.", "@", "\"", ";", "=")):
        return True
    # Drop all-stopwords fragments
    if all(w in {"the", "and", "or", "for", "of", "in", "on", "to", "with", "is", "are", "by", "from", "at", "as", "be"} for w in words):
        return True
    return False


def infer_node_type(label: str, context_texts: Sequence[str], default_type: str = "Concept") -> str:
    """Classify entity label + evidence snippets into controlled Knowledge Graph node types."""
    if default_type and default_type not in ("Concept", "Entity"):
        return default_type

    low = label.lower()
    joined = f"{low} " + " ".join(context_texts[:3]).lower()

    if any(k in low for k in ("attack", "flood", "hijacking", "spoofing", "injection", "dos", "ddos", "malware", "phishing", "exploit")):
        return "Attack"
    if low in {"syn", "syn-ack", "ack", "tcp", "udp", "ip", "http", "https", "tls", "ssl", "dns", "arp", "bgp", "smtp", "ssh", "icmp"} or any(
        k in low for k in ("protocol", "handshake", "packet", "sequence number")
    ):
        return "Protocol"
    if any(k in low for k in ("cookie", "cookies", "firewall", "filtering", "bcp 38", "mitigation", "defense", "defence", "rate limit", "encryption", "authentication")):
        return "Defense"
    if any(k in low for k in ("dataset", "benchmark", "corpus", "imagenet", "glue", "squad", "mnist", "cifar")):
        return "Dataset"
    if any(k in low for k in ("accuracy", "f1", "precision", "recall", "bleu", "rouge", "latency", "throughput", "rmse", "auc", "score", "metric", "rate")):
        return "Metric"
    if any(k in low for k in ("roberta", "bert", "gpt", "llama", "transformer", "lstm", "cnn", "resnet", "neural network", "classifier", "llm")):
        return "Model"
    if any(k in low for k in ("algorithm", "method", "technique", "pipeline", "framework", "architecture", "attention")):
        return "Method"
    if any(k in low for k in ("server", "client", "queue", "backlog", "tcb", "control block", "database", "engine", "network", "memory", "router")):
        return "System"
    if any(k in low for k in ("exhaustion", "vulnerability", "bottleneck", "shortage", "failure")):
        return "Problem"
    if any(k in joined for k in ("mitigates", "prevents", "protects against")) and "attack" not in low:
        return "Defense"
    return default_type or "Concept"


def _add_candidate(
    pool: Dict[str, Dict[str, Any]],
    *,
    label: str,
    node_type: str = "Concept",
    priority: float = 1.0,
    alias: Optional[str] = None,
    description: Optional[str] = None,
    source: str = "text",
) -> None:
    cleaned = _clean_candidate_label(label)
    if _is_generic_or_noisy(cleaned):
        return
    key = _canonical_dedup_key(cleaned)
    if not key or len(key) < 2:
        return

    entry = pool.get(key)
    if entry is None:
        aliases = [cleaned]
        if alias and alias.strip() and alias.strip().lower() != cleaned.lower():
            aliases.append(alias.strip())
        pool[key] = {
            "label": cleaned,
            "normalized_label": key,
            "node_type": node_type,
            "priority": priority,
            "aliases": aliases,
            "description": description,
            "sources": {source},
        }
    else:
        entry["priority"] += priority * 0.45
        entry["sources"].add(source)
        # Prefer richer capitalization/surface form
        if len(cleaned) > len(entry["label"]) and cleaned.lower().startswith(entry["label"].lower()):
            entry["label"] = cleaned
        if cleaned not in entry["aliases"]:
            entry["aliases"].append(cleaned)
        if alias and alias.strip() and alias.strip() not in entry["aliases"]:
            entry["aliases"].append(alias.strip())
        if node_type not in ("Concept", "Entity") and entry["node_type"] in ("Concept", "Entity"):
            entry["node_type"] = node_type
        if description and not entry["description"]:
            entry["description"] = description


def _merge_research_paper_candidates(
    pool: Dict[str, Dict[str, Any]],
    document: Document,
    db: Session,
) -> bool:
    """Reuse cached ResearchPaperAnalysis read-only when present to enrich academic entities."""
    analysis = (
        db.query(ResearchPaperAnalysis)
        .filter(
            ResearchPaperAnalysis.document_id == document.id,
            ResearchPaperAnalysis.user_id == document.user_id,
        )
        .order_by(ResearchPaperAnalysis.id.desc())
        .first()
    )
    if not analysis:
        return False

    research_context = getattr(analysis, "research_context", None) or getattr(analysis, "research_context_json", None) or {}
    methodology = getattr(analysis, "methodology", None) or getattr(analysis, "methodology_json", None) or {}
    evaluation = getattr(analysis, "evaluation", None) or getattr(analysis, "evaluation_json", None) or {}
    conclusion = getattr(analysis, "conclusion", None) or getattr(analysis, "conclusion_json", None) or {}

    added = False

    def _consume_list(items: Any, ntype: str, prio: float) -> None:
        nonlocal added
        if isinstance(items, str):
            items = [items]
        if not isinstance(items, list):
            return
        for item in items[:5]:
            if isinstance(item, dict):
                txt = str(item.get("label") or item.get("name") or item.get("value") or item.get("text") or "").strip()
            else:
                txt = str(item or "").strip()
            if not txt:
                continue
            # Trim long sentences to concise concept phrases for graph readability
            short = txt.split(":")[0].split(",")[0].strip()
            if len(short) > 65:
                short = " ".join(short.split()[:7]).strip(" .,-;:")
            if not _is_generic_or_noisy(short):
                _add_candidate(pool, label=short, node_type=ntype, priority=prio, source="research_analysis")
                added = True

    _consume_list(research_context.get("problem_statement"), "Problem", 3.0)
    _consume_list(methodology.get("proposed_method") or methodology.get("key_techniques"), "Method", 3.2)
    _consume_list(methodology.get("models") or methodology.get("architectures"), "Model", 3.0)
    _consume_list(methodology.get("datasets") or evaluation.get("datasets"), "Dataset", 3.0)
    _consume_list(evaluation.get("metrics"), "Metric", 2.9)
    _consume_list(evaluation.get("baselines"), "Method", 2.5)
    _consume_list(evaluation.get("key_results"), "Result", 2.6)
    _consume_list(conclusion.get("limitations"), "Limitation", 2.4)
    _consume_list(conclusion.get("future_work"), "FutureWork", 2.2)

    return added


def extract_grounded_nodes(
    *,
    document: Document,
    db: Session,
    units: Sequence[ChunkUnit],
    spans: Sequence[SentenceSpan],
    section_hierarchy: Sequence[Dict[str, Any]],
    max_nodes: int = 32,
) -> Dict[str, Any]:
    """
    Extract, deduplicate, ground, and rank typed knowledge graph nodes from unified
    Cognidocs document units. Every surviving node has verified document evidence.
    """
    pool: Dict[str, Dict[str, Any]] = {}
    acronym_map: Dict[str, str] = {}

    used_research_analysis = _merge_research_paper_candidates(pool, document, db)

    # 1. Reuse existing HandwrittenConcept rows when present (without regenerating)
    if document.is_handwritten:
        hw_concepts = (
            db.query(HandwrittenConcept)
            .filter(
                HandwrittenConcept.document_id == document.id,
                HandwrittenConcept.user_id == document.user_id,
            )
            .all()
        )
        for row in hw_concepts[:25]:
            _add_candidate(
                pool,
                label=row.name,
                node_type="Concept",
                priority=2.2,
                description=row.definition,
                source="handwritten_concept",
            )

    full_clean_text = "\n".join(sp.text for sp in spans) or (document.extracted_text or "")

    # 2. Acronym definitions: "Denial-of-Service (DoS)" -> primary + alias
    for full_form, acronym in _ACRONYM_DEF_RE.findall(full_clean_text):
        full_clean = _clean_candidate_label(full_form)
        if _is_generic_or_noisy(full_clean) or acronym in _ACRONYM_STOPWORDS:
            continue
        # Trim leading lowercase determiners like "a "
        full_clean = re.sub(r"^(?:a|an|the|in|for|of|with)\s+", "", full_clean, flags=re.IGNORECASE).strip()
        if not _is_generic_or_noisy(full_clean):
            acronym_map[acronym.upper()] = _canonical_dedup_key(full_clean)
            _add_candidate(
                pool,
                label=full_clean,
                alias=acronym,
                priority=2.6,
                source="acronym_def",
            )

    # 3. Section headings from hierarchy and markdown headers
    for sec in section_hierarchy[:25]:
        sec_title = _clean_candidate_label(str(sec.get("title") or ""))
        if sec_title and sec_title.lower() not in NOISE_TOKENS:
            _add_candidate(pool, label=sec_title, priority=2.0, source="section_heading")

    for unit in units:
        for hdr in _HEADING_RE.findall(unit.content or ""):
            cleaned_hdr = _clean_candidate_label(hdr)
            if cleaned_hdr and cleaned_hdr.lower() not in NOISE_TOKENS:
                _add_candidate(pool, label=cleaned_hdr, priority=2.1, source="markdown_heading")

    # 4. Definition subjects ("SYN Flood is a denial-of-service attack")
    for subj in _DEF_SUBJECT_RE.findall(full_clean_text):
        subj_clean = _clean_candidate_label(subj)
        if not _is_generic_or_noisy(subj_clean):
            _add_candidate(pool, label=subj_clean, priority=2.7, source="definition")

    # 5. Reused Cognidocs baseline concept extractor + capitalized phrases + technical acronyms
    dummy_chunks = [
        type("ChunkAdapter", (), {"content": u.content, "page_number": u.page})()
        for u in units
    ]
    try:
        for c_dict in extract_standard_concepts_fallback(full_clean_text, dummy_chunks):
            c_name = c_dict.get("name") if isinstance(c_dict, dict) else str(c_dict)
            if c_name:
                _add_candidate(pool, label=c_name, priority=1.3, source="mindmap_fallback")
    except Exception:
        pass

    phrase_counts: Dict[str, int] = {}
    for phrase in _CAP_PHRASE_RE.findall(full_clean_text):
        cleaned = _clean_candidate_label(phrase)
        if _is_generic_or_noisy(cleaned):
            continue
        k = _canonical_dedup_key(cleaned)
        phrase_counts[k] = phrase_counts.get(k, 0) + 1
        if phrase_counts[k] >= 2 or len(cleaned.split()) >= 2:
            _add_candidate(pool, label=cleaned, priority=1.1 + min(1.5, 0.25 * phrase_counts[k]), source="cap_phrase")

    acronym_counts: Dict[str, int] = {}
    for acr in _TECH_ACRONYM_RE.findall(full_clean_text):
        if acr in _ACRONYM_STOPWORDS or len(acr) < 2:
            continue
        acronym_counts[acr] = acronym_counts.get(acr, 0) + 1
    for acr, cnt in acronym_counts.items():
        if cnt >= 2 or acr in acronym_map:
            if acr in acronym_map and acronym_map[acr] in pool:
                existing = pool[acronym_map[acr]]
                if acr not in existing["aliases"]:
                    existing["aliases"].append(acr)
                existing["priority"] += min(1.2, 0.2 * cnt)
            else:
                _add_candidate(pool, label=acr, priority=1.5 + min(1.5, 0.25 * cnt), source="acronym")

    # 6. Merge acronym alias entries if standalone acronym also entered pool
    for acr, full_key in list(acronym_map.items()):
        acr_key = _canonical_dedup_key(acr)
        if acr_key in pool and full_key in pool and acr_key != full_key:
            target = pool[full_key]
            src = pool.pop(acr_key)
            for al in src["aliases"]:
                if al not in target["aliases"]:
                    target["aliases"].append(al)
            target["priority"] += src["priority"] * 0.5

    # 7. Ground every candidate against real document spans (drop ungrounded!)
    valid_chunk_ids: Set[Optional[int]] = {u.chunk_id for u in units}
    max_page = max((int(u.page or 1) for u in units), default=1)
    grounded_candidates: List[Dict[str, Any]] = []
    rejected_ungrounded = 0
    sentence_index = build_sentence_inverted_index(spans)

    for key, item in pool.items():
        evidence, pages = find_entity_evidence(
            item["label"],
            item["aliases"],
            spans,
            units,
            max_items=4,
            sentence_index=sentence_index,
        )
        evidence = sanitize_evidence_list(evidence, valid_chunk_ids, max_page)
        if not evidence:
            rejected_ungrounded += 1
            continue

        # Enforce stricter centrality for bare architectural nouns like "Server" or "Client"
        if item["normalized_label"] in {"server", "client", "network", "user", "attack"} and len(evidence) < 2 and len(pages) < 2:
            if item["priority"] < 2.2:
                continue

        ev_texts = [e["excerpt"] for e in evidence]
        resolved_type = infer_node_type(item["label"], ev_texts, item["node_type"])
        ev_count = len(evidence)
        confidence = round(min(0.97, 0.56 + 0.11 * min(ev_count, 3) + 0.04 * min(len(item["sources"]), 3)), 3)

        grounded_candidates.append(
            {
                "raw_key": key,
                "label": item["label"],
                "normalized_label": key,
                "node_type": resolved_type,
                "description": item.get("description") or ev_texts[0][:180],
                "aliases": sorted({a for a in item["aliases"] if a.lower() != item["label"].lower()}),
                "confidence": confidence,
                "evidence": evidence,
                "evidence_count": ev_count,
                "source_pages": pages or [ev["page"] for ev in evidence],
                "score": item["priority"] + 0.65 * ev_count + (0.8 if len(pages) > 1 else 0.0),
                "sources": sorted(item["sources"]),
            }
        )

    # 8. Hybrid lexical + embedding deduplication (merge high-similarity surface variants)
    grounded_candidates.sort(key=lambda c: (-c["score"], -c["evidence_count"], c["label"]))
    candidate_pool = grounded_candidates[: max(max_nodes * 2, 48)]
    embeddings: List[Optional[List[float]]] = []
    for cand in candidate_pool:
        try:
            embeddings.append(generate_embedding(f"{cand['label']} {' '.join(cand['aliases'][:2])}"))
        except Exception:
            embeddings.append(None)

    deduped: List[Dict[str, Any]] = []
    dedup_vecs: List[Optional[List[float]]] = []
    merged_duplicates = 0

    for cand, vec in zip(candidate_pool, embeddings):
        merged_into = None
        cand_tokens = set(cand["normalized_label"].split())
        for idx, keeper in enumerate(deduped):
            keep_tokens = set(keeper["normalized_label"].split())
            if not cand_tokens or not keep_tokens:
                continue
            token_overlap = len(cand_tokens & keep_tokens) / max(len(cand_tokens | keep_tokens), 1)
            contains_same = (
                cand["normalized_label"] in keeper["normalized_label"]
                or keeper["normalized_label"] in cand["normalized_label"]
            )
            # Never merge complementary/contrasting terms like Client vs Server, SYN vs SYN-ACK, Precision vs Recall
            sim = cosine_similarity(vec, dedup_vecs[idx]) if (vec and dedup_vecs[idx]) else 0.0
            should_merge = (
                cand["normalized_label"] == keeper["normalized_label"]
                or (contains_same and token_overlap >= 0.5 and sim >= 0.80)
                or (token_overlap >= 0.65 and sim >= 0.88)
            )
            if should_merge:
                merged_into = keeper
                break

        if merged_into is not None:
            merged_duplicates += 1
            for extra_alias in [cand["label"], *cand["aliases"]]:
                if extra_alias.lower() != merged_into["label"].lower() and extra_alias not in merged_into["aliases"]:
                    merged_into["aliases"].append(extra_alias)
            merged_into["score"] += cand["score"] * 0.25
            existing_pages = set(merged_into["source_pages"]) | set(cand["source_pages"])
            merged_into["source_pages"] = sorted(existing_pages)
            merged_sigs = {e["excerpt"][:70].lower() for e in merged_into["evidence"]}
            for ev in cand["evidence"]:
                if ev["excerpt"][:70].lower() not in merged_sigs and len(merged_into["evidence"]) < 5:
                    merged_into["evidence"].append(ev)
                    merged_sigs.add(ev["excerpt"][:70].lower())
            merged_into["evidence_count"] = len(merged_into["evidence"])
        else:
            deduped.append(cand)
            dedup_vecs.append(vec)

    # Final top max_nodes assignment + stable unique node_keys
    final_nodes: List[Dict[str, Any]] = []
    used_keys: Set[str] = set()
    max_score = max((n["score"] for n in deduped), default=1.0) or 1.0

    for cand in deduped[:max_nodes]:
        slug = re.sub(r"[^a-z0-9]+", "_", cand["normalized_label"]).strip("_")[:60] or f"node_{len(final_nodes)+1}"
        node_key = slug
        suffix = 2
        while node_key in used_keys:
            node_key = f"{slug}_{suffix}"
            suffix += 1
        used_keys.add(node_key)

        conf = round(cand["confidence"], 3)
        tier = "high" if conf >= 0.75 else ("medium" if conf >= 0.50 else "low")
        final_nodes.append(
            {
                "node_key": node_key,
                "label": cand["label"],
                "normalized_label": cand["normalized_label"],
                "node_type": cand["node_type"],
                "description": cand["description"],
                "aliases": cand["aliases"][:6],
                "confidence": conf,
                "confidence_tier": tier,
                "importance_score": round(min(1.0, cand["score"] / max_score), 3),
                "evidence_count": len(cand["evidence"]),
                "source_pages": sorted({int(p) for p in cand["source_pages"]}),
                "evidence": cand["evidence"],
                "metadata": {
                    "sources": cand["sources"],
                },
            }
        )

    return {
        "nodes": final_nodes,
        "used_research_analysis": used_research_analysis,
        "diagnostics": {
            "candidate_pool_size": len(pool),
            "rejected_ungrounded_nodes": rejected_ungrounded,
            "merged_duplicate_nodes": merged_duplicates,
            "final_node_count": len(final_nodes),
        },
    }