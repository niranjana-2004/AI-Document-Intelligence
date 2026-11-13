from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException
import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.models.research_paper_analysis import ResearchPaperAnalysis
from app.models.knowledge_intelligence_cache import (
    KnowledgeIntelligenceCache,
    compute_ki_cache_key,
)
from app.schemas.cross_document_knowledge_graph import (
    CanonicalEntityOut,
    CrossDocumentEdgeOut,
    SelectedDocumentInfo,
)
from app.schemas.knowledge_intelligence import (
    ConflictItem,
    CrossDocumentInsight,
    DirectAnswer,
    IntelligenceEvidenceItem,
    IntelligenceRelationship,
    KnowledgeIntelligenceQueryRequest,
    KnowledgeIntelligenceResponse,
    KnowledgeOverviewItem,
    RelatedTopicItem,
)
from app.services.cross_document_entity_resolution import (
    DISALLOWED_MERGE_PAIRS,
    DOMAIN_CONTEXT_MARKERS,
    extract_acronym_candidates,
    normalize_concept_label,
)
from app.services.cross_document_graph_service import (
    get_or_generate_cross_document_graph,
)
from app.services.knowledge_graph_evidence_service import (
    assemble_substantive_document_units,
    clean_excerpt_text,
)
from app.services.knowledge_graph_service import (
    _effective_content_hash,
)

logger = logging.getLogger(__name__)

# Stopwords for query understanding
QUERY_STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "to", "from", "up",
    "down", "of", "off", "over", "under", "again", "further", "then", "once", "here", "there",
    "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "can", "will", "just", "don", "should", "now", "what", "which", "who", "whom", "this",
    "that", "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "having", "do", "does", "did", "doing", "would", "could", "tell", "me",
    "explain", "say", "does", "documents", "document", "collection", "knows", "cognidocs",
    "everything", "topic", "concept", "regarding", "discuss", "discussed", "show", "find",
    "look", "see", "mean", "meaning", "define", "definition", "and", "or", "but", "if", "also",
    "terms", "term", "either", "neither",
}

# Opposing claim tokens for contradiction detection
CONTRADICTION_PAIRS = [
    (r"\bconnection[- ]oriented\b", r"\bconnectionless\b"),
    (r"\breliable\b", r"\bunreliable\b"),
    (r"\bsymmetric\b", r"\basymmetric\b"),
    (r"\blossless\b", r"\blossy\b"),
    (r"\bencrypted\b", r"\b(?:unencrypted|plaintext)\b"),
    (r"\bsynchronous\b", r"\basynchronous\b"),
    (r"\bdeterministic\b", r"\b(?:nondeterministic|stochastic)\b"),
    (r"\bcentralized\b", r"\b(?:decentralized|distributed)\b"),
]


def parse_knowledge_query(
    raw_query: str,
    focus_entity_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministic first-pass query analyzer.
    Extracts intent, candidate entities, acronyms, and comparison/relationship flags.
    """
    q_str = (raw_query or "").strip()
    q_lower = q_str.lower()

    # Intent detection rules
    intent = "knowledge_lookup"
    is_conflict = bool(
        re.search(r"\b(disagree|conflict|contradict|difference between documents|what changed)\b", q_lower)
    )
    is_comparison = bool(
        re.search(r"\b(compare|difference between|versus|\bvs\b|how do .* differ)\b", q_lower)
    )
    is_relationship = bool(
        re.search(r"\b(related|relationship|connect|how does .* use|how are .* connected|interact)\b", q_lower)
    )
    is_evidence = bool(
        re.search(r"\b(show me evidence|all the evidence|evidence for|where is .* discussed|citations|cite)\b", q_lower)
    )
    is_synthesis = bool(
        re.search(r"\b(what do my documents say|explain everything|synthesize|across my documents|shared by)\b", q_lower)
    )

    if is_conflict:
        intent = "conflict_detection"
    elif is_comparison:
        intent = "entity_comparison"
    elif is_relationship:
        intent = "relationship_query"
    elif is_evidence:
        intent = "evidence_audit"
    elif is_synthesis:
        intent = "cross_document_synthesis"

    # Acronym extraction (uppercase words 2-8 chars)
    acronyms = [m for m in re.findall(r"\b[A-Z0-9]{2,8}\b", q_str) if not m.isdigit()]

    # Candidate phrases extraction
    # Strip common interrogative boilerplates
    cleaned_q = re.sub(
        r"^(what (do my documents say about|does cognidocs know about|is|are|does)|explain (everything cognidocs knows about|everything about|all about)|how (are|does|do)|show me (all the evidence for|evidence for)|compare|tell me about)\s+",
        "",
        q_lower,
    )
    cleaned_q = re.sub(r"[?!.,;:\"']+", " ", cleaned_q).strip()

    tokens = [t for t in re.findall(r"\b[a-zA-Z0-9_-]+\b", cleaned_q) if t not in QUERY_STOPWORDS]

    candidate_entities: List[str] = []
    if focus_entity_override:
        candidate_entities.append(focus_entity_override)

    for acr in acronyms:
        if acr.lower() not in [c.lower() for c in candidate_entities]:
            candidate_entities.append(acr)

    # Add 1-word, 2-word, and 3-word ngrams from remaining tokens
    for i in range(len(tokens)):
        candidate_entities.append(tokens[i])
        if i + 1 < len(tokens):
            candidate_entities.append(f"{tokens[i]} {tokens[i+1]}")
        if i + 2 < len(tokens):
            candidate_entities.append(f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}")

    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique_candidates: List[str] = []
    for c in candidate_entities:
        c_clean = c.strip()
        if c_clean and len(c_clean) >= 2 and c_clean.lower() not in seen:
            seen.add(c_clean.lower())
            unique_candidates.append(c_clean)

    return {
        "raw_query": q_str,
        "normalized_query": cleaned_q,
        "intent": intent,
        "candidate_entities": unique_candidates,
        "acronyms": acronyms,
        "relationship_requested": is_relationship or is_comparison,
        "comparison_requested": is_comparison,
        "evidence_requested": is_evidence,
        "conflict_requested": is_conflict,
    }


def match_query_to_canonical_entities(
    candidate_entities: List[str],
    canonical_entities: List[CanonicalEntityOut],
    raw_query: str = "",
) -> List[CanonicalEntityOut]:
    """
    Match query candidate phrases against canonical entities from the cross-document graph.
    Enforces strict disallowed merge pairs and polysemy disambiguation.
    """
    if not canonical_entities:
        return []

    q_lower = raw_query.lower()
    scored_matches: List[Tuple[float, CanonicalEntityOut]] = []

    for cent in canonical_entities:
        c_name = cent.canonical_name
        c_norm = cent.normalized_name
        c_aliases = [a.lower() for a in cent.aliases]
        c_acrs = [a.lower() for a in extract_acronym_candidates(c_name)]

        best_score = 0.0

        for cand in candidate_entities:
            cand_clean = cand.strip()
            cand_norm = normalize_concept_label(cand_clean)
            cand_lower = cand_clean.lower()

            # Disallowed merge pair check
            is_disallowed = False
            for pair in DISALLOWED_MERGE_PAIRS:
                if cand_norm in pair and c_norm in pair and cand_norm != c_norm:
                    is_disallowed = True
                    break
            if is_disallowed:
                continue

            # Polysemy check (e.g. Java programming vs Java island, Apple tech vs fruit)
            for p_key, domain_dict in DOMAIN_CONTEXT_MARKERS.items():
                if re.search(rf"\b{re.escape(p_key)}\b", c_norm) or re.search(rf"\b{re.escape(p_key)}\b", cand_norm):
                    query_domains = {dom for dom, markers in domain_dict.items() if any(m in q_lower for m in markers)}
                    if query_domains:
                        occ_text = (cent.description or "").lower() + " " + " ".join(
                            (occ.source_text or "").lower() for occ in getattr(cent, "occurrences", [])
                        ) + " " + c_norm
                        entity_domains = {dom for dom, markers in domain_dict.items() if any(m in occ_text for m in markers)}
                        if entity_domains and not (query_domains & entity_domains):
                            best_score = 0.0
                            is_disallowed = True
                            break
            if is_disallowed:
                continue

            # Exact match
            if cand_norm == c_norm or cand_lower == c_name.lower():
                score = 1.0 + (0.2 if cent.is_shared else 0.0)
                best_score = max(best_score, score)
                continue

            # Acronym match
            if cand_lower in c_acrs or cand_clean.upper() in [a.upper() for a in cent.aliases]:
                score = 0.95 + (0.2 if cent.is_shared else 0.0)
                best_score = max(best_score, score)
                continue

            # Alias match
            if cand_norm in c_aliases or cand_lower in c_aliases:
                score = 0.90 + (0.1 if cent.is_shared else 0.0)
                best_score = max(best_score, score)
                continue

            # Whole word token match in canonical name or normalized name (e.g. "tcp" in "the tcp protocol is")
            if (len(cand_norm) >= 3 or cand_clean.isupper()) and cand_norm not in QUERY_STOPWORDS and re.search(rf"\b{re.escape(cand_norm)}\b", c_norm):
                score = 0.88 + (0.1 if cent.is_shared else 0.0)
                best_score = max(best_score, score)
                continue

            # Substring / token containment
            if len(cand_norm) >= 3 and (cand_norm in c_norm or c_norm in cand_norm):
                # Guard against short spurious prefixes: e.g. "cat" in "category"
                len_ratio = min(len(cand_norm), len(c_norm)) / max(len(cand_norm), len(c_norm))
                if len_ratio >= 0.4:
                    score = 0.70 * len_ratio + (0.1 if cent.is_shared else 0.0)
                    best_score = max(best_score, score)

        if best_score >= 0.5:
            # Combine with entity importance score
            final_score = best_score * 0.7 + cent.importance_score * 0.3
            scored_matches.append((final_score, cent))

    scored_matches.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_matches]


def retrieve_multi_source_evidence(
    db: Session,
    user_id: int,
    documents: List[Document],
    target_entities: List[CanonicalEntityOut],
    all_canonical_entities: List[CanonicalEntityOut],
    edges: List[CrossDocumentEdgeOut],
    max_evidence_items: int = 20,
) -> List[IntelligenceEvidenceItem]:
    """
    Retrieve and unify source evidence from:
    1. CrossDocumentKnowledgeGraph entity occurrences
    2. ResearchPaperAnalysis sections and claims (if paper analyzer ran)
    3. HandwrittenPage transcription lines (if document is handwritten)
    4. DocumentChunk text units
    Deduplicates and deterministically scores evidence items.
    """
    evidence_items: List[IntelligenceEvidenceItem] = []
    seen_keys: Set[str] = set()

    doc_map = {d.id: d for d in documents}
    target_names = {e.canonical_name.lower() for e in target_entities}
    target_keys = {e.entity_key for e in target_entities}
    target_norms = {e.normalized_name for e in target_entities}

    # 1. Harvest occurrences from target entities
    for cent in target_entities:
        for occ in cent.occurrences:
            doc = doc_map.get(occ.document_id)
            if not doc:
                continue

            doc_title = getattr(doc, "title", None) or doc.filename or f"Document #{doc.id}"
            cleaned_text = clean_excerpt_text(occ.source_text or "")
            if not cleaned_text or len(cleaned_text) < 10:
                continue

            excerpt_hash = hashlib.md5(f"{doc.id}:{occ.page_number}:{cleaned_text[:60]}".encode("utf-8")).hexdigest()
            if excerpt_hash in seen_keys:
                continue
            seen_keys.add(excerpt_hash)

            source_type = "document_chunk"
            if doc.is_handwritten or getattr(doc, "document_type", "") == "handwritten":
                source_type = "handwritten"
            elif getattr(doc, "document_type", "") == "research_paper":
                source_type = "research_paper"
            elif (doc.filename or "").lower().endswith(".pdf"):
                source_type = "printed_pdf"
            elif (doc.filename or "").lower().endswith((".txt", ".docx")):
                source_type = "text_document"

            evidence_items.append(
                IntelligenceEvidenceItem(
                    id=f"occ-{occ.id or len(evidence_items)+1}",
                    document_id=doc.id,
                    document_title=doc_title,
                    page_number=max(1, occ.page_number or 1),
                    chunk_id=occ.chunk_id,
                    source_type=source_type,
                    excerpt=cleaned_text,
                    entity=cent.canonical_name,
                    relationship=None,
                    confidence=float(occ.resolution_confidence or 0.85),
                    section=occ.evidence.get("section") if isinstance(occ.evidence, dict) else None,
                )
            )

    # 2. Harvest evidence from connected edges
    for edge in edges:
        if edge.source_key in target_keys or edge.target_key in target_keys:
            for ev in edge.evidence:
                d_id = ev.get("document_id")
                doc = doc_map.get(d_id)
                if not doc:
                    continue

                doc_title = getattr(doc, "title", None) or doc.filename or f"Document #{doc.id}"
                raw_snippet = ev.get("snippet", "")
                cleaned_text = clean_excerpt_text(raw_snippet)
                if not cleaned_text or len(cleaned_text) < 10:
                    continue

                page = ev.get("page", 1)
                excerpt_hash = hashlib.md5(f"{doc.id}:{page}:{cleaned_text[:60]}".encode("utf-8")).hexdigest()
                if excerpt_hash in seen_keys:
                    continue
                seen_keys.add(excerpt_hash)

                source_type = "document_chunk"
                if doc.is_handwritten:
                    source_type = "handwritten"
                elif (doc.filename or "").lower().endswith(".pdf"):
                    source_type = "printed_pdf"

                evidence_items.append(
                    IntelligenceEvidenceItem(
                        id=f"edge-ev-{len(evidence_items)+1}",
                        document_id=doc.id,
                        document_title=doc_title,
                        page_number=max(1, int(page or 1)),
                        chunk_id=ev.get("chunk_id"),
                        source_type=source_type,
                        excerpt=cleaned_text,
                        entity=edge.source_key.split(":")[-1].replace("_", " ").title(),
                        relationship=f"{edge.relationship} -> {edge.target_key.split(':')[-1].replace('_', ' ').title()}",
                        confidence=float(edge.confidence or 0.75),
                        section=ev.get("section"),
                    )
                )

    # 3. Harvest from ResearchPaperAnalysis if doc is research paper and has analysis
    for doc in documents:
        rpa = (
            db.query(ResearchPaperAnalysis)
            .filter(
                ResearchPaperAnalysis.document_id == doc.id,
                ResearchPaperAnalysis.user_id == user_id,
            )
            .order_by(ResearchPaperAnalysis.id.desc())
            .first()
        )
        if not rpa:
            continue

        doc_title = getattr(doc, "title", None) or doc.filename or f"Document #{doc.id}"
        # Inspect sections and methodology for target terms
        for sec_name, sec_data in [
            ("methodology", rpa.methodology),
            ("evaluation", rpa.evaluation),
            ("conclusion", rpa.conclusion),
            ("research_context", rpa.research_context),
        ]:
            if not isinstance(sec_data, dict):
                continue
            text_block = sec_data.get("summary") or sec_data.get("description") or ""
            if not text_block:
                continue
            text_lower = text_block.lower()

            for t_norm in target_norms:
                if t_norm in text_lower:
                    cleaned_text = clean_excerpt_text(text_block)
                    excerpt_hash = hashlib.md5(f"{doc.id}:rpa:{cleaned_text[:60]}".encode("utf-8")).hexdigest()
                    if excerpt_hash not in seen_keys:
                        seen_keys.add(excerpt_hash)
                        evidence_items.append(
                            IntelligenceEvidenceItem(
                                id=f"rpa-{len(evidence_items)+1}",
                                document_id=doc.id,
                                document_title=doc_title,
                                page_number=1,
                                chunk_id=None,
                                source_type="research_paper",
                                excerpt=cleaned_text,
                                entity=t_norm.title(),
                                relationship=f"analyzed in {sec_name}",
                                confidence=0.92,
                                section=sec_name.title(),
                            )
                        )

    # 4. Harvest from HandwrittenPage if handwritten
    for doc in documents:
        if not (doc.is_handwritten or getattr(doc, "document_type", "") == "handwritten"):
            continue

        doc_title = getattr(doc, "title", None) or doc.filename or f"Document #{doc.id}"
        hw_pages = (
            db.query(HandwrittenPage)
            .filter(HandwrittenPage.document_id == doc.id)
            .order_by(HandwrittenPage.page_number.asc())
            .all()
        )
        for hwp in hw_pages:
            content = (hwp.edited_transcription or hwp.raw_transcription or "").strip()
            if not content:
                continue
            content_lower = content.lower()
            for t_norm in target_norms:
                if t_norm in content_lower:
                    # Extract matching sentence/line
                    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
                    matching_lines = [ln for ln in lines if t_norm in ln.lower()]
                    excerpt_sample = " ".join(matching_lines[:2]) if matching_lines else content[:200]
                    cleaned_text = clean_excerpt_text(excerpt_sample)

                    excerpt_hash = hashlib.md5(f"{doc.id}:{hwp.page_number}:{cleaned_text[:60]}".encode("utf-8")).hexdigest()
                    if excerpt_hash not in seen_keys:
                        seen_keys.add(excerpt_hash)
                        raw_conf = float(hwp.confidence_score or 0.88)
                        norm_conf = min(1.0, max(0.0, raw_conf / 100.0 if raw_conf > 1.0 else raw_conf))
                        evidence_items.append(
                            IntelligenceEvidenceItem(
                                id=f"hw-{hwp.id or len(evidence_items)+1}",
                                document_id=doc.id,
                                document_title=doc_title,
                                page_number=max(1, hwp.page_number or 1),
                                chunk_id=None,
                                source_type="handwritten",
                                excerpt=cleaned_text,
                                entity=t_norm.title(),
                                relationship=None,
                                confidence=round(norm_conf, 2),
                                section="Handwritten Note",
                            )
                        )

    # Deterministic ranking
    def rank_evidence(item: IntelligenceEvidenceItem) -> float:
        score = item.confidence * 0.4
        item_lower = item.excerpt.lower()
        if any(t in item_lower for t in target_norms):
            score += 0.4
        if item.source_type == "research_paper":
            score += 0.1
        elif item.source_type == "handwritten":
            score += 0.08
        return score

    evidence_items.sort(key=rank_evidence, reverse=True)
    return evidence_items[:max_evidence_items]


def detect_cross_document_insights_and_conflicts(
    target_entities: List[CanonicalEntityOut],
    all_canonical_entities: List[CanonicalEntityOut],
    evidence: List[IntelligenceEvidenceItem],
    documents: List[Document],
) -> Tuple[List[CrossDocumentInsight], List[ConflictItem]]:
    """
    Detect shared knowledge across documents, unique document contributions,
    and conservative contradictions / differing emphases.
    """
    insights: List[CrossDocumentInsight] = []
    conflicts: List[ConflictItem] = []

    doc_map = {d.id: (getattr(d, "title", None) or d.filename or f"Document #{d.id}") for d in documents}

    # Group evidence by entity and document
    entity_doc_evidence: Dict[str, Dict[int, List[IntelligenceEvidenceItem]]] = {}
    for ev in evidence:
        ent = ev.entity
        entity_doc_evidence.setdefault(ent, {}).setdefault(ev.document_id, []).append(ev)

    for cent in target_entities:
        c_name = cent.canonical_name
        doc_ev_map = entity_doc_evidence.get(c_name, {})

        # If entity appears across multiple documents
        if cent.is_shared or len(doc_ev_map) > 1 or cent.document_count > 1:
            doc_names = [doc_map.get(d_id, f"Doc #{d_id}") for d_id in (doc_ev_map.keys() or [d.document_id for d in cent.documents])]

            # 1. Synthesize Shared Knowledge Insight
            doc_summaries: List[str] = []
            for d_id, items in doc_ev_map.items():
                d_title = doc_map.get(d_id, f"Doc #{d_id}")
                top_ex = items[0].excerpt[:140] if items else ""
                if top_ex:
                    doc_summaries.append(f"In {d_title}: \"{top_ex}...\"")

            shared_desc = f"{c_name} is discussed across {len(doc_names)} documents ({', '.join(doc_names)}). "
            if doc_summaries:
                shared_desc += " ".join(doc_summaries[:3])

            insights.append(
                CrossDocumentInsight(
                    entity=c_name,
                    insight_type="shared_knowledge",
                    description=shared_desc,
                    document_names=doc_names,
                    confidence=0.88,
                )
            )

            # 2. Check for Differences / Conflicts
            if len(doc_ev_map) >= 2:
                doc_ids_list = list(doc_ev_map.keys())
                for i in range(len(doc_ids_list)):
                    for j in range(i + 1, len(doc_ids_list)):
                        d1 = doc_ids_list[i]
                        d2 = doc_ids_list[j]
                        d1_name = doc_map.get(d1, f"Doc #{d1}")
                        d2_name = doc_map.get(d2, f"Doc #{d2}")

                        t1_items = doc_ev_map[d1]
                        t2_items = doc_ev_map[d2]
                        t1_text = " ".join(item.excerpt.lower() for item in t1_items)
                        t2_text = " ".join(item.excerpt.lower() for item in t2_items)

                        # Check explicit opposing claims (contradiction)
                        contradiction_found = False
                        for pos_re, neg_re in CONTRADICTION_PAIRS:
                            has_pos_1 = bool(re.search(pos_re, t1_text))
                            has_neg_1 = bool(re.search(neg_re, t1_text))
                            has_pos_2 = bool(re.search(pos_re, t2_text))
                            has_neg_2 = bool(re.search(neg_re, t2_text))

                            if (has_pos_1 and has_neg_2) or (has_neg_1 and has_pos_2):
                                contradiction_found = True
                                conflicts.append(
                                    ConflictItem(
                                        entity=c_name,
                                        category="contradiction",
                                        description=(
                                            f"Contradictory assertions detected regarding {c_name} between "
                                            f"{d1_name} and {d2_name}."
                                        ),
                                        claim_a={
                                            "document_id": d1,
                                            "document_name": d1_name,
                                            "page": t1_items[0].page_number if t1_items else 1,
                                            "statement": t1_items[0].excerpt[:180] if t1_items else "",
                                        },
                                        claim_b={
                                            "document_id": d2,
                                            "document_name": d2_name,
                                            "page": t2_items[0].page_number if t2_items else 1,
                                            "statement": t2_items[0].excerpt[:180] if t2_items else "",
                                        },
                                        confidence=0.85,
                                    )
                                )
                                break

                        # If no contradiction, check different emphasis vs agreement
                        if not contradiction_found:
                            # If both discuss the concept with substantive excerpts
                            d1_keywords = set(re.findall(r"\b[a-z]{4,}\b", t1_text)) - QUERY_STOPWORDS
                            d2_keywords = set(re.findall(r"\b[a-z]{4,}\b", t2_text)) - QUERY_STOPWORDS
                            overlap = len(d1_keywords & d2_keywords)
                            total_vocab = len(d1_keywords | d2_keywords) or 1
                            jaccard = overlap / total_vocab

                            if jaccard < 0.25 and len(d1_keywords) > 5 and len(d2_keywords) > 5:
                                conflicts.append(
                                    ConflictItem(
                                        entity=c_name,
                                        category="different_emphasis",
                                        description=(
                                            f"{d1_name} and {d2_name} emphasize different aspects of {c_name}. "
                                            f"{d1_name} highlights {', '.join(list(d1_keywords - d2_keywords)[:3])}, "
                                            f"whereas {d2_name} focuses on {', '.join(list(d2_keywords - d1_keywords)[:3])}."
                                        ),
                                        claim_a={
                                            "document_id": d1,
                                            "document_name": d1_name,
                                            "page": t1_items[0].page_number if t1_items else 1,
                                            "statement": t1_items[0].excerpt[:160] if t1_items else "",
                                        },
                                        claim_b={
                                            "document_id": d2,
                                            "document_name": d2_name,
                                            "page": t2_items[0].page_number if t2_items else 1,
                                            "statement": t2_items[0].excerpt[:160] if t2_items else "",
                                        },
                                        confidence=0.78,
                                    )
                                )
                            else:
                                conflicts.append(
                                    ConflictItem(
                                        entity=c_name,
                                        category="agreement",
                                        description=f"{d1_name} and {d2_name} present consistent descriptions of {c_name}.",
                                        claim_a={
                                            "document_id": d1,
                                            "document_name": d1_name,
                                            "page": t1_items[0].page_number if t1_items else 1,
                                            "statement": t1_items[0].excerpt[:140] if t1_items else "",
                                        },
                                        claim_b={
                                            "document_id": d2,
                                            "document_name": d2_name,
                                            "page": t2_items[0].page_number if t2_items else 1,
                                            "statement": t2_items[0].excerpt[:140] if t2_items else "",
                                        },
                                        confidence=0.82,
                                    )
                                )
        else:
            # Document-specific entity
            doc_id = cent.documents[0].document_id if cent.documents else (list(doc_ev_map.keys())[0] if doc_ev_map else None)
            if doc_id:
                d_name = doc_map.get(doc_id, f"Doc #{doc_id}")
                insights.append(
                    CrossDocumentInsight(
                        entity=c_name,
                        insight_type="document_specific",
                        description=f"{c_name} is specifically discussed in {d_name} and does not appear prominently in other selected documents.",
                        document_names=[d_name],
                        confidence=0.85,
                    )
                )

    return insights, conflicts


def _deterministic_synthesize_answer(
    query: str,
    target_entities: List[CanonicalEntityOut],
    evidence: List[IntelligenceEvidenceItem],
    insights: List[CrossDocumentInsight],
    conflicts: List[ConflictItem],
    selected_documents: List[Document],
) -> DirectAnswer:
    """
    Deterministic synthesis for when Ollama is offline or skip_llm=True.
    Produces high-precision grounded answers citing exact document titles and page numbers.
    """
    if not evidence:
        return DirectAnswer(
            text="Cognidocs could not find sufficient evidence in your selected documents to answer this question. Try selecting additional documents or refining your query.",
            confidence=0.0,
            grounding_status="insufficient_evidence",
            supporting_sources=[],
            synthesis_method="deterministic_fallback",
        )

    lines: List[str] = []
    cited_sources: List[str] = []

    # 1. Topic Overview
    ent_names = [e.canonical_name for e in target_entities[:3]]
    if ent_names:
        lines.append(f"Based on your documents, here is the verified intelligence regarding **{', '.join(ent_names)}**:")
    else:
        lines.append("Based on your selected documents, the following grounded intelligence was retrieved:")

    # 2. Key evidence statements with exact citations
    top_items = evidence[:5]
    for idx, ev in enumerate(top_items):
        cite_str = f"[Doc: {ev.document_title}, p.{ev.page_number}]"
        cited_sources.append(f"{ev.document_title} (p.{ev.page_number})")
        # Format clean bullet
        snippet = ev.excerpt.strip().rstrip(".")
        if len(snippet) > 220:
            snippet = snippet[:220].rsplit(" ", 1)[0] + "..."
        lines.append(f"- **{ev.entity}**: \"{snippet}\" {cite_str}")

    # 3. Cross-document synthesis note
    shared_insights = [ins for ins in insights if ins.insight_type == "shared_knowledge"]
    if shared_insights:
        lines.append("")
        lines.append(f"**Cross-Document Synthesis**: {shared_insights[0].description}")

    # 4. Conflict / Agreement note
    contradictions = [c for c in conflicts if c.category == "contradiction"]
    if contradictions:
        lines.append("")
        lines.append(f"**Discrepancy Note**: {contradictions[0].description}")

    text_body = "\n".join(lines)
    return DirectAnswer(
        text=text_body,
        confidence=0.88,
        grounding_status="grounded",
        supporting_sources=list(dict.fromkeys(cited_sources)),
        synthesis_method="deterministic_fallback",
    )


def synthesize_grounded_answer(
    query: str,
    target_entities: List[CanonicalEntityOut],
    evidence: List[IntelligenceEvidenceItem],
    insights: List[CrossDocumentInsight],
    conflicts: List[ConflictItem],
    selected_documents: List[Document],
    skip_llm: bool = False,
) -> DirectAnswer:
    """
    Synthesize grounded answer using local Ollama (llama3.2).
    If Ollama is unavailable, times out, or hallucinates, cleanly falls back
    to deterministic grounded synthesis.
    """
    if not evidence:
        return DirectAnswer(
            text="Cognidocs could not find enough information in your selected documents to answer this question.",
            confidence=0.0,
            grounding_status="insufficient_evidence",
            supporting_sources=[],
            synthesis_method="deterministic_fallback",
        )

    if skip_llm:
        return _deterministic_synthesize_answer(
            query, target_entities, evidence, insights, conflicts, selected_documents
        )

    # Build bounded prompt for Ollama
    evidence_prompt_lines: List[str] = []
    valid_citation_keys: Set[str] = set()

    for idx, ev in enumerate(evidence[:8]):
        marker = f"[Source {idx+1} | Document: {ev.document_title} | Page: {ev.page_number}]"
        evidence_prompt_lines.append(f"{marker}\n{ev.excerpt}\n")
        valid_citation_keys.add(f"{ev.document_title.lower()}:{ev.page_number}")

    evidence_context = "\n".join(evidence_prompt_lines)

    insights_summary = ""
    if insights:
        insights_summary = "CROSS-DOCUMENT INSIGHTS:\n" + "\n".join(f"- {ins.description}" for ins in insights[:3]) + "\n\n"

    conflicts_summary = ""
    if conflicts:
        conflicts_summary = "OBSERVED DIFFERENCES / CONFLICTS:\n" + "\n".join(f"- {c.category.upper()}: {c.description}" for c in conflicts[:2]) + "\n\n"

    system_prompt = (
        "You are the Cognidocs Knowledge Intelligence engine.\n"
        "Your task is to answer the user's question directly, clearly, and factually using ONLY the supplied SOURCES.\n\n"
        "STRICT GROUNDING RULES:\n"
        "1. Every factual statement MUST be derived exclusively from the provided sources.\n"
        "2. Cite your sources using exact inline citation tags such as [Doc: <Title>, p.<Page>] matching the header labels.\n"
        "3. Do not invent any facts, page numbers, titles, or concepts.\n"
        "4. If the sources do not provide enough evidence to answer fully, state clearly what is known and what is missing.\n"
        "5. Keep the response focused, structured with markdown bullets, and professional."
    )

    full_prompt = (
        f"{system_prompt}\n\n"
        f"SOURCES:\n{evidence_context}\n\n"
        f"{insights_summary}"
        f"{conflicts_summary}"
        f"USER QUESTION:\n{query}\n\n"
        f"GROUNDED ANSWER:\n"
    )

    try:
        ollama_url = settings.ollama_generate_url
        model_name = settings.OLLAMA_MODEL
        resp = requests.post(
            ollama_url,
            json={
                "model": model_name,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 450,
                },
            },
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            ans_text = (data.get("response") or "").strip()
            if ans_text and len(ans_text) >= 20:
                # Grounding validation: ensure no disallowed hallucinated entities
                for pair in DISALLOWED_MERGE_PAIRS:
                    p_list = list(pair)
                    # If query was about p_list[0] and not p_list[1], check if p_list[1] was hallucinated
                    q_lower = query.lower()
                    if p_list[0] in q_lower and p_list[1] not in q_lower:
                        # Check if p_list[1] appears in response without being in any evidence
                        if p_list[1] in ans_text.lower() and not any(p_list[1] in ev.excerpt.lower() for ev in evidence):
                            logger.warning("Rejecting Ollama answer due to hallucinated disallowed pair: %s", p_list[1])
                            return _deterministic_synthesize_answer(
                                query, target_entities, evidence, insights, conflicts, selected_documents
                            )

                # Extract supporting sources cited
                cited_sources: List[str] = []
                for ev in evidence:
                    if (
                        f"p.{ev.page_number}" in ans_text
                        or ev.document_title.lower() in ans_text.lower()
                        or f"[Doc: {ev.document_title}" in ans_text
                    ):
                        cited_sources.append(f"{ev.document_title} (p.{ev.page_number})")

                if not cited_sources:
                    for ev in evidence[:3]:
                        cited_sources.append(f"{ev.document_title} (p.{ev.page_number})")

                return DirectAnswer(
                    text=ans_text,
                    confidence=0.88,
                    grounding_status="grounded",
                    supporting_sources=list(dict.fromkeys(cited_sources)),
                    synthesis_method="ollama",
                )
    except Exception as exc:
        logger.info("Ollama synthesis unavailable (%s); falling back to deterministic synthesis", exc)

    return _deterministic_synthesize_answer(
        query, target_entities, evidence, insights, conflicts, selected_documents
    )


def execute_knowledge_intelligence_query(
    db: Session,
    *,
    user_id: int,
    request: KnowledgeIntelligenceQueryRequest,
) -> KnowledgeIntelligenceResponse:
    """
    Main orchestration function for Knowledge Intelligence / Personal Knowledge Explorer.
    1. Authenticates & verifies tenant document ownership
    2. Checks cache
    3. Analyzes query intent and extracts focus candidate entities
    4. Retrieves cross-document knowledge graph & canonical entities
    5. Resolves query candidate terms to canonical entities
    6. Aggregates multi-source evidence (PDF, Handwritten, Research, Text)
    7. Synthesizes cross-document insights and conservative conflicts
    8. Synthesizes grounded answer (Ollama llama3.2 with deterministic fallback)
    9. Caches and returns structured response
    """
    t_start = time.perf_counter()
    timings: Dict[str, float] = {}

    clean_query = (request.query or "").strip()
    if len(clean_query) < 2:
        raise HTTPException(status_code=400, detail="Query must contain at least 2 non-whitespace characters.")

    # 1. Enforce strict document ownership
    requested_ids = sorted(list(set(request.document_ids)))
    if requested_ids:
        docs = (
            db.query(Document)
            .filter(Document.id.in_(requested_ids), Document.user_id == user_id)
            .all()
        )
        if len(docs) != len(requested_ids):
            raise HTTPException(
                status_code=404,
                detail="One or more selected documents do not exist or are not owned by the current user",
            )
    else:
        # Default to all user documents (up to 12 most recent)
        docs = (
            db.query(Document)
            .filter(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .limit(12)
            .all()
        )
        if not docs:
            raise HTTPException(
                status_code=400,
                detail="No documents available in your library. Please upload or select documents to query.",
            )

    selected_doc_ids = sorted([d.id for d in docs])
    doc_map = {d.id: d for d in docs}

    # 2. Compute Content Hashes & Check Cache
    doc_hashes: Dict[int, str] = {}
    for d in docs:
        try:
            _, _, _, _, base_h = assemble_substantive_document_units(d, db)
            doc_hashes[d.id] = _effective_content_hash(d, db, base_h)
        except Exception:
            doc_hashes[d.id] = str(getattr(d, "id", 0))

    combined_hash = hashlib.sha256(
        ":".join(f"{d_id}:{doc_hashes.get(d_id, '')}" for d_id in selected_doc_ids).encode("utf-8")
    ).hexdigest()

    parsed_query = parse_knowledge_query(request.query, request.focus_entity)
    timings["query_parsing_ms"] = round((time.perf_counter() - t_start) * 1000, 2)

    cache_key = compute_ki_cache_key(
        user_id=user_id,
        document_ids=selected_doc_ids,
        combined_content_hash=combined_hash,
        normalized_query=parsed_query["normalized_query"],
        focus_entity=request.focus_entity,
        include_low_conf=request.include_low_confidence,
        skip_llm=request.skip_llm,
    )

    if not request.force_refresh:
        cached_entry = (
            db.query(KnowledgeIntelligenceCache)
            .filter(
                KnowledgeIntelligenceCache.user_id == user_id,
                KnowledgeIntelligenceCache.cache_key == cache_key,
            )
            .first()
        )
        if cached_entry and cached_entry.response_json:
            try:
                cached_data = dict(cached_entry.response_json)
                cached_data["cached"] = True
                return KnowledgeIntelligenceResponse(**cached_data)
            except Exception as e:
                logger.warning("Error parsing cached knowledge intelligence: %s", e)

    # 3. Retrieve or generate Cross-Document Knowledge Graph
    t_retrieval_start = time.perf_counter()
    cd_graph_res = get_or_generate_cross_document_graph(
        db=db,
        user_id=user_id,
        document_ids=selected_doc_ids,
        force_refresh=False,
        include_low_confidence=request.include_low_confidence,
        skip_llm=True,  # graph generation uses fast deterministic extraction
        max_nodes=60,
    )

    canonical_entities = getattr(cd_graph_res, "entities", getattr(cd_graph_res, "canonical_entities", []))
    edges = getattr(cd_graph_res, "edges", [])

    # 4. Entity Resolution
    t_er_start = time.perf_counter()
    resolved_target_entities = match_query_to_canonical_entities(
        candidate_entities=parsed_query["candidate_entities"],
        canonical_entities=canonical_entities,
        raw_query=request.query,
    )

    # If no specific target entity was matched:
    # If the user asked a general/broad collection query (e.g., "overview", "what are the main concepts shared"),
    # provide the top collection entities.
    # If the user asked about specific concepts that do NOT exist in the collection, keep target entities empty
    # so strict grounding reports insufficient evidence.
    is_broad_overview_query = (
        not parsed_query["candidate_entities"]
        or any(w in parsed_query["normalized_query"] for w in ["overview", "main concepts", "shared concepts", "all concepts"])
    )

    if not resolved_target_entities and is_broad_overview_query:
        sorted_entities = sorted(
            canonical_entities,
            key=lambda e: (e.is_shared, e.importance_score, e.occurrence_count),
            reverse=True,
        )
        resolved_target_entities = sorted_entities[:4]

    timings["entity_resolution_ms"] = round((time.perf_counter() - t_er_start) * 1000, 2)

    # 5. Retrieve Multi-Source Evidence
    t_ev_start = time.perf_counter()
    evidence = retrieve_multi_source_evidence(
        db=db,
        user_id=user_id,
        documents=docs,
        target_entities=resolved_target_entities,
        all_canonical_entities=canonical_entities,
        edges=edges,
        max_evidence_items=request.max_evidence_items,
    )
    timings["evidence_retrieval_ms"] = round((time.perf_counter() - t_ev_start) * 1000, 2)
    timings["total_retrieval_ms"] = round((time.perf_counter() - t_retrieval_start) * 1000, 2)

    # 6. Detect Cross-Document Insights & Differences
    insights, conflicts = detect_cross_document_insights_and_conflicts(
        target_entities=resolved_target_entities,
        all_canonical_entities=canonical_entities,
        evidence=evidence,
        documents=docs,
    )

    # 7. Synthesize Grounded Direct Answer
    t_llm_start = time.perf_counter()
    direct_answer = synthesize_grounded_answer(
        query=request.query,
        target_entities=resolved_target_entities,
        evidence=evidence,
        insights=insights,
        conflicts=conflicts,
        selected_documents=docs,
        skip_llm=request.skip_llm,
    )
    timings["llm_synthesis_ms"] = round((time.perf_counter() - t_llm_start) * 1000, 2)

    # 8. Build Knowledge Overview Items
    knowledge_overview: List[KnowledgeOverviewItem] = []
    target_keys = {e.entity_key for e in resolved_target_entities}
    for e in resolved_target_entities:
        doc_names = [doc_map[d.document_id].filename for d in e.documents if d.document_id in doc_map]
        knowledge_overview.append(
            KnowledgeOverviewItem(
                canonical_name=e.canonical_name,
                entity_key=e.entity_key,
                entity_type=e.entity_type,
                document_count=e.document_count,
                mention_count=e.occurrence_count,
                is_shared=e.is_shared,
                documents=doc_names,
                document_ids=[d.document_id for d in e.documents if d.document_id in doc_map],
                importance_score=round(e.importance_score, 2),
            )
        )

    # 9. Build Relevant Relationships
    relationships: List[IntelligenceRelationship] = []
    seen_rel_pairs: Set[str] = set()
    for edge in edges:
        if edge.source_key in target_keys or edge.target_key in target_keys:
            rel_pair = f"{edge.source_key}:{edge.relationship}:{edge.target_key}"
            if rel_pair in seen_rel_pairs:
                continue
            seen_rel_pairs.add(rel_pair)

            src_name = edge.source_key.split(":")[-1].replace("_", " ").title()
            tgt_name = edge.target_key.split(":")[-1].replace("_", " ").title()
            doc_titles = [doc_map[d_id].filename for d_id in edge.supporting_document_ids if d_id in doc_map]

            relationships.append(
                IntelligenceRelationship(
                    source_entity=src_name,
                    target_entity=tgt_name,
                    predicate=edge.relationship,
                    confidence=round(edge.confidence, 2),
                    supporting_documents=doc_titles,
                    supporting_document_ids=edge.supporting_document_ids,
                    evidence_snippets=[ev.get("snippet", "") for ev in edge.evidence[:2] if isinstance(ev, dict)],
                    is_cross_document=edge.is_cross_document,
                )
            )

    # 10. Related Topics
    related_topics: List[RelatedTopicItem] = []
    connected_keys: Set[str] = set()
    for edge in edges:
        if edge.source_key in target_keys and edge.target_key not in target_keys:
            connected_keys.add(edge.target_key)
        elif edge.target_key in target_keys and edge.source_key not in target_keys:
            connected_keys.add(edge.source_key)

    for cent in canonical_entities:
        if cent.entity_key in connected_keys and cent.entity_key not in target_keys:
            related_topics.append(
                RelatedTopicItem(
                    name=cent.canonical_name,
                    entity_key=cent.entity_key,
                    relationship_to_focus="connected concept",
                    document_count=cent.document_count,
                )
            )
            if len(related_topics) >= 8:
                break

    # 11. Format Selected Documents Info
    selected_docs_info: List[SelectedDocumentInfo] = [
        SelectedDocumentInfo(
            document_id=d.id,
            title=getattr(d, "title", None) or d.filename or f"Document #{d.id}",
            filename=d.filename or "",
            document_type=getattr(d, "document_type", "pdf"),
            page_count=getattr(d, "text_length", 1) // 500 or 1,
            is_handwritten=bool(d.is_handwritten),
        )
        for d in docs
    ]

    total_time_ms = round((time.perf_counter() - t_start) * 1000, 2)
    timings["total_latency_ms"] = total_time_ms

    stats = {
        "selected_documents_count": len(docs),
        "total_canonical_entities": len(canonical_entities),
        "target_entities_count": len(resolved_target_entities),
        "evidence_items_count": len(evidence),
        "relationships_count": len(relationships),
        "insights_count": len(insights),
        "conflicts_count": len(conflicts),
        "cached": False,
    }

    diagnostics = {
        "intent": parsed_query["intent"],
        "candidate_entities": parsed_query["candidate_entities"],
        "timings": timings,
        "synthesis_method": direct_answer.synthesis_method,
    }

    response_payload = KnowledgeIntelligenceResponse(
        query=request.query,
        normalized_query=parsed_query["normalized_query"],
        intent=parsed_query["intent"],
        focus_entities=[e.canonical_name for e in resolved_target_entities],
        selected_document_ids=selected_doc_ids,
        selected_documents=selected_docs_info,
        direct_answer=direct_answer,
        knowledge_overview=knowledge_overview,
        relationships=relationships,
        evidence=evidence,
        cross_document_insights=insights,
        conflicts=conflicts,
        related_topics=related_topics,
        stats=stats,
        diagnostics=diagnostics,
        cached=False,
    )

    # 12. Save to Cache
    try:
        # Delete existing stale cache if any
        db.query(KnowledgeIntelligenceCache).filter(
            KnowledgeIntelligenceCache.user_id == user_id,
            KnowledgeIntelligenceCache.cache_key == cache_key,
        ).delete(synchronize_session=False)

        new_cache = KnowledgeIntelligenceCache(
            user_id=user_id,
            cache_key=cache_key,
            selected_doc_ids_json=selected_doc_ids,
            combined_content_hash=combined_hash,
            query_text=request.query,
            focus_entity=request.focus_entity,
            response_json=json.loads(response_payload.model_dump_json()),
        )
        db.add(new_cache)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Could not persist knowledge intelligence cache: %s", e)

    return response_payload
