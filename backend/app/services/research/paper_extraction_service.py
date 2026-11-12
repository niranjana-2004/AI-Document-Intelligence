from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.research_paper import MISSING_FIELD_TEXT
from app.services.handwriting.ollama_client import OllamaError, query_ollama_json
from app.services.research.paper_evidence_service import (
    EvidenceTracker,
    detect_figure_or_table_in_text,
    extract_verbatim_excerpt,
    missing_field,
)
from app.services.research.paper_section_service import ChunkUnit

logger = logging.getLogger(__name__)

_HEADER_BOILERPLATE_RE = re.compile(
    r"^(?:journal\s+of\b|international\s+journal\b|proceedings\s+of\b|issn\b|isbn\b|doi\b|www\.|http|page\s*\|\s*\d+|to\s+cite\s+this|volume\s+\d+|issue\s+\d+|©|\d{4}$)",
    re.IGNORECASE,
)


def _first_sentences(text: str, keywords: List[str], max_sentences: int = 2) -> List[str]:
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if not clean:
        return []
    sents = re.split(r"(?<=[.!?])\s+", clean)
    hits: List[str] = []
    for sent in sents:
        s_clean = sent.strip()
        if len(s_clean) < 25 or len(s_clean) > 420:
            continue
        if re.search(r"\.{3,}|\bpage\s*\|\s*\d+", s_clean, re.I):
            continue
        low = s_clean.lower()
        if any(re.search(kw, low) for kw in keywords):
            hits.append(s_clean)
            if len(hits) >= max_sentences:
                break
    return hits


def _find_evidence_in_units(
    units: List[ChunkUnit],
    keywords: List[str],
    preferred_roles: Optional[Set[str]] = None,
    max_hits: int = 2,
) -> List[Tuple[ChunkUnit, str]]:
    """
    Search ordered chunks prioritizing preferred section roles, returning
    matching (ChunkUnit, sentence_or_excerpt) pairs.
    """
    ordered = (
        sorted(units, key=lambda u: (0 if (preferred_roles and u.normalized_role in preferred_roles) else 1, u.chunk_index))
        if preferred_roles
        else units
    )
    results: List[Tuple[ChunkUnit, str]] = []
    seen_snippets: Set[str] = set()
    for u in ordered:
        sents = _first_sentences(u.content, keywords, max_sentences=max_hits)
        for s in sents:
            sig = s[:70].lower()
            if sig not in seen_snippets:
                seen_snippets.add(sig)
                results.append((u, s))
                if len(results) >= max_hits:
                    return results
    return results


def _extract_basic_information(units: List[ChunkUnit], tracker: EvidenceTracker) -> Dict[str, Any]:
    if not units:
        return {
            "title": missing_field(),
            "authors": missing_field(),
            "affiliation": missing_field(),
            "abstract": missing_field(),
            "keywords": missing_field(),
            "publication_info": missing_field(),
        }

    front_units = [u for u in units if u.page <= 4][:8] or units[:4]
    front_text = "\n".join(u.content for u in front_units[:3])

    # 1. Title detection
    title_field = missing_field()
    cite_title = re.search(r'[“"]([^"”\n]{12,180})[”"]', front_text)
    if cite_title:
        t_val = re.sub(r"\s+", " ", cite_title.group(1)).strip()
        src_u = next((u for u in front_units[:3] if t_val[:25].lower() in u.content.lower()), front_units[0])
        title_field = tracker.make_field(t_val, unit=src_u, fact_type="explicit", confidence=0.92, excerpt_override=t_val)
    else:
        for u in front_units[:2]:
            lines = [ln.strip() for ln in u.content.splitlines() if ln.strip()]
            candidates: List[str] = []
            for idx, ln in enumerate(lines[:14]):
                if _HEADER_BOILERPLATE_RE.match(ln):
                    continue
                if "@" in ln or re.match(r"^(?:abstract|by\s+|1\.\s+introduction|table\s+of\s+contents)\b", ln, re.I):
                    break
                if 10 <= len(ln) <= 180 and not re.match(r"^page\s+\d+$", ln, re.I):
                    # Join wrapped second title line if short/contiguous before 'by ...'
                    if idx + 1 < len(lines) and re.match(r"^by\s+", lines[idx + 1], re.I) is None and not candidates:
                        next_ln = lines[idx + 1].strip()
                        if (
                            5 <= len(next_ln) <= 65
                            and not _HEADER_BOILERPLATE_RE.match(next_ln)
                            and "@" not in next_ln
                            and not re.match(r"^(?:by|bachelor|master|department|faculty|university|abstract)\b", next_ln, re.I)
                            and idx + 2 < len(lines)
                            and re.match(r"^by\b", lines[idx + 2], re.I)
                        ):
                            candidates.append(f"{ln} {next_ln}")
                            break
                    candidates.append(ln)
                    break
            if candidates:
                t_val = re.sub(r"\s+", " ", candidates[0]).strip(" :-")
                title_field = tracker.make_field(t_val, unit=u, fact_type="explicit", confidence=0.87, excerpt_override=t_val)
                break

    # 2. Authors detection
    authors_field = missing_field()
    thesis_by = re.search(r"\bby\s*\n\s*([A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+){1,4})\b", front_text)
    cite_authors = re.search(
        r"(?:to\s+cite\s+this\s+article\s*\n\s*)([^\n“\"]{5,220})",
        front_text,
        re.IGNORECASE,
    )
    explicit_authors = re.search(r"(?:^|\n)\s*authors?\s*[:\-]\s*([^\n]{4,180})", front_text, re.IGNORECASE)
    if explicit_authors:
        val = re.sub(r"\s+", " ", explicit_authors.group(1)).strip()
        src_u = next((u for u in front_units[:3] if explicit_authors.group(1)[:15] in u.content), front_units[0])
        authors_field = tracker.make_field(val, unit=src_u, fact_type="explicit", confidence=0.92)
    elif thesis_by:
        val = thesis_by.group(1).strip()
        src_u = next((u for u in front_units[:3] if val in u.content), front_units[0])
        authors_field = tracker.make_field(val, unit=src_u, fact_type="explicit", confidence=0.91, excerpt_override=f"by {val}")
    elif cite_authors:
        raw_auth = re.sub(r"\s+\d+\b", "", cite_authors.group(1))
        val = re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", raw_auth)).strip(" ,")
        if len(val) >= 5:
            src_u = next((u for u in front_units[:3] if "to cite this article" in u.content.lower()), front_units[0])
            authors_field = tracker.make_field(val, unit=src_u, fact_type="explicit", confidence=0.9)

    # 3. Affiliation detection
    affiliation_field = missing_field()
    for u in front_units[:4]:
        aff_lines = [
            ln.strip()
            for ln in u.content.splitlines()
            if re.search(
                r"\b(?:university|college|institute|department\s+of|faculty\s+of|school\s+of|laboratory|polytechnic)\b",
                ln,
                re.I,
            )
            and len(ln.strip()) >= 12
            and not re.search(r"\.{3,}", ln)
        ]
        if aff_lines:
            val = "; ".join(dict.fromkeys(aff_lines[:3]))[:240]
            affiliation_field = tracker.make_field(
                val,
                unit=u,
                fact_type="explicit",
                confidence=0.86,
                excerpt_override=aff_lines[0][:220],
            )
            break

    # 4. Abstract detection
    abstract_field = missing_field()
    abs_units = [
        u
        for u in units[:12]
        if u.normalized_role == "abstract" or re.search(r"(?:^|\n)\s*abstract\b[:\s—\-]*", u.content, re.I)
    ]
    if abs_units:
        first_abs_u = abs_units[0]
        idx_start = units.index(first_abs_u)
        collected: List[str] = []
        for u in units[idx_start : min(len(units), idx_start + 3)]:
            txt = u.content
            m_abs = re.search(r"(?:^|\n)\s*abstract\b[:\s—\-]*([\s\S]+)", txt, re.I)
            seg = m_abs.group(1) if m_abs else txt
            # Stop if we hit next section heading
            stop = re.search(
                r"\n\s*(?:keywords?|index\s+terms?|dedication|acknowledg(?:e)?ments?|1\.?\s+introduction|i\.\s+introduction|table\s+of\s+contents)\b",
                seg,
                re.I,
            )
            if stop:
                collected.append(seg[: stop.start()].strip())
                break
            collected.append(seg.strip())
            if len(" ".join(collected)) > 1400:
                break
        abs_val = re.sub(r"\s+", " ", " ".join(collected)).strip()
        # Reject single-word ToC line "Abstract ii"
        if len(abs_val) >= 60 and not re.match(r"^[ivxlcdm\d]+\b", abs_val, re.I):
            abs_summary = abs_val[:850] + ("..." if len(abs_val) > 850 else "")
            abstract_field = tracker.make_field(
                abs_summary,
                unit=first_abs_u,
                fact_type="explicit",
                confidence=0.93,
                excerpt_override=abs_val[:220],
            )

    # 5. Keywords detection
    keywords_field = missing_field()
    for u in front_units[:6]:
        kw_m = re.search(r"\b(?:keywords?|index\s+terms?)\s*[:—\-]\s*([^\n]{5,240})", u.content, re.I)
        if kw_m:
            kw_val = re.sub(r"\s+", " ", kw_m.group(1)).strip(" .;")
            keywords_field = tracker.make_field(
                kw_val,
                unit=u,
                fact_type="explicit",
                confidence=0.92,
                excerpt_override=kw_m.group(0)[:220],
            )
            break

    # 6. Publication metadata
    pub_field = missing_field()
    for u in front_units[:4]:
        pub_bits: List[str] = []
        m_journal = re.search(r"([^\n]*(?:journal|proceedings|transactions|conference|symposium|arxiv)[^\n]{0,90})", u.content, re.I)
        if m_journal:
            pub_bits.append(m_journal.group(1).strip())
        m_issn = re.search(r"(ISSN\s*:\s*[\w\-]+(?:\s+Volume\s+\d+(?:,\s*Issue\s+\d+)?)?(?:\s*\([^)]+\))?)", u.content, re.I)
        if m_issn:
            pub_bits.append(m_issn.group(1).strip())
        m_doi = re.search(r"(DOI\s*:\s*\S+)", u.content, re.I)
        if m_doi:
            pub_bits.append(m_doi.group(1).strip())
        m_thesis = re.search(r"(A\s+Thesis\s+Submitted[^\n]{10,140}(?:\n[^\n]{5,90})?)", u.content, re.I)
        if m_thesis and not pub_bits:
            pub_bits.append(re.sub(r"\s+", " ", m_thesis.group(1)).strip())

        if pub_bits:
            val = " | ".join(dict.fromkeys(pub_bits))[:260]
            pub_field = tracker.make_field(
                val,
                unit=u,
                fact_type="explicit",
                confidence=0.91,
                excerpt_override=val[:220],
            )
            break

    return {
        "title": title_field,
        "authors": authors_field,
        "affiliation": affiliation_field,
        "abstract": abstract_field,
        "keywords": keywords_field,
        "publication_info": pub_field,
    }


def _extract_numerical_data(units: List[ChunkUnit], tracker: EvidenceTracker) -> List[Dict[str, Any]]:
    """
    Extract reported quantitative metrics, dataset sizes, splits, parameter counts, and
    latency/performance figures while preserving exact original values and units.
    Also compute deterministic `derived` improvement deltas only when explicit pairs exist.
    """
    findings: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str, int]] = set()

    metric_patterns: List[Tuple[str, re.Pattern[str], Optional[str]]] = [
        ("Accuracy", re.compile(r"\baccuracy\b[^.\n]{0,40}?[:=isof\s]+(\d{1,3}(?:\.\d+)?)\s*(%)", re.I), "%"),
        ("Precision", re.compile(r"\bprecision\b[^.\n]{0,35}?[:=isof\s]+(\d{1,3}(?:\.\d+)?)\s*(%|)", re.I), None),
        ("Recall", re.compile(r"\brecall\b[^.\n]{0,35}?[:=isof\s]+(\d{1,3}(?:\.\d+)?)\s*(%|)", re.I), None),
        ("F1-Score", re.compile(r"\bf1[\-\s]?score\b[^.\n]{0,35}?[:=isof\s]+(\d{1,3}(?:\.\d+)?)\s*(%|)", re.I), None),
        ("AUC / ROC-AUC", re.compile(r"\b(?:roc[\-\s]?)?auc\b[^.\n]{0,30}?[:=isof\s]+(\d+(?:\.\d+)?)\s*(%|)", re.I), None),
        ("Loss", re.compile(r"\b(?:training|validation|test|final)?\s*loss\b[^.\n]{0,25}?[:=]\s*(\d+\.\d+)", re.I), "loss"),
        (
            "Dataset / Sample Count",
            re.compile(
                r"\b(\d{1,3}(?:,\d{3})+|\d{3,7})\s+(?:[a-z\-]+\s+){0,2}(samples?|records?|images?|instances?|documents?|lines?|entries|nodes|packets|examples)\b",
                re.I,
            ),
            "count",
        ),
        (
            "Train/Test Split",
            re.compile(r"\b(?:train(?:ing)?[\s/\-]+test(?:\s+split)?|split(?:\s+ratio)?)\b[^.\n]{0,35}?(\d{2}\s*[:/]\s*\d{2}(?:\s*[:/]\s*\d{2})?|\d{2}%\s*(?:train|training))", re.I),
            "ratio",
        ),
        (
            "Parameter Count",
            re.compile(r"\b(\d+(?:\.\d+)?)\s*(million|billion|[mbk])\s+parameters?\b", re.I),
            "parameters",
        ),
        (
            "Runtime / Latency",
            re.compile(r"\b(?:latency|runtime|execution\s+time|encryption\s+time|inference\s+time|time\s+taken)\b[^.\n]{0,40}?[:=isof\s]+(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|sec|seconds?|minutes?|hrs?)\b", re.I),
            None,
        ),
        (
            "Throughput / Bandwidth",
            re.compile(r"\b(?:throughput|speed)\b[^.\n]{0,35}?[:=isof\s]+(\d+(?:\.\d+)?)\s*(mb/s|gb/s|kb/s|iops|ops/s|req/s)\b", re.I),
            None,
        ),
        (
            "Improvement / Speedup",
            re.compile(r"\b(\d+(?:\.\d+)?)\s*(%|x)\s+(?:faster|improvement|higher|reduction|speedup)\b", re.I),
            None,
        ),
    ]

    for u in units:
        if u.normalized_role == "references":
            continue
        sentences = re.split(r"(?<=[.!?])\s+|\n+", u.content)
        for sent in sentences:
            s_clean = re.sub(r"\s+", " ", sent).strip()
            if len(s_clean) < 12 or len(s_clean) > 360 or re.search(r"\.{3,}", s_clean):
                continue

            for m_name, pat, default_unit in metric_patterns:
                for m in pat.finditer(s_clean):
                    val_str = m.group(1).strip()
                    raw_unit = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
                    if default_unit == "count" and raw_unit:
                        unit_label = raw_unit.lower()
                        orig_val = val_str
                    elif default_unit == "parameters" and raw_unit:
                        unit_label = f"{raw_unit} parameters"
                        orig_val = f"{val_str} {raw_unit}"
                    elif raw_unit == "%":
                        unit_label = "%"
                        orig_val = f"{val_str}%"
                    elif raw_unit:
                        unit_label = raw_unit
                        orig_val = f"{val_str} {raw_unit}".strip()
                    else:
                        unit_label = default_unit
                        orig_val = val_str

                    dedup = (m_name, orig_val.lower(), u.page)
                    if dedup in seen_keys:
                        continue
                    seen_keys.add(dedup)

                    fig_tab = detect_figure_or_table_in_text(s_clean)
                    ev_id, src = tracker.register_evidence(
                        claim=f"{m_name}: {orig_val} ({s_clean[:120]})",
                        unit=u,
                        fact_type="explicit",
                        confidence=0.91,
                        excerpt_override=s_clean[:230],
                        figure_or_table=fig_tab,
                    )
                    findings.append(
                        {
                            "id": f"num-{len(findings) + 1}",
                            "metric_name": m_name,
                            "original_value": orig_val,
                            "unit": unit_label,
                            "experimental_context": s_clean[:220],
                            "fact_type": "explicit",
                            "source": src,
                            "evidence_id": ev_id,
                            "confidence": 0.91,
                        }
                    )
                    if len(findings) >= 25:
                        break
                if len(findings) >= 25:
                    break

            # Deterministic paired comparison delta within same sentence (explicit % vs explicit %)
            pair_m = re.search(
                r"\baccuracy\b[^.\n]{0,40}?\b(\d{2}(?:\.\d+)?)\s*%[^.\n]{0,60}?\b(?:baseline|compared\s+to|versus|vs\.?|from)\b[^.\n]{0,30}?\b(\d{2}(?:\.\d+)?)\s*%",
                s_clean,
                re.I,
            )
            if pair_m and len(findings) < 25:
                v1, v2 = float(pair_m.group(1)), float(pair_m.group(2))
                if v1 != v2 and abs(v1 - v2) <= 50.0:
                    delta = round(v1 - v2, 2)
                    sign = "+" if delta > 0 else ""
                    delta_val = f"{sign}{delta} percentage points"
                    ev_id, src = tracker.register_evidence(
                        claim=f"Accuracy delta ({delta_val} between {v1}% and {v2}%)",
                        unit=u,
                        fact_type="derived",
                        confidence=0.89,
                        excerpt_override=s_clean[:230],
                    )
                    findings.append(
                        {
                            "id": f"num-{len(findings) + 1}",
                            "metric_name": "Derived Accuracy Delta",
                            "original_value": delta_val,
                            "unit": "percentage points",
                            "experimental_context": s_clean[:220],
                            "fact_type": "derived",
                            "source": src,
                            "evidence_id": ev_id,
                            "confidence": 0.89,
                        }
                    )
            if len(findings) >= 25:
                break
        if len(findings) >= 25:
            break

    return findings


def _extract_tables_and_figures(units: List[ChunkUnit]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, int]] = set()
    ref_pat = re.compile(r"\b(Table|Figure|Fig\.|Algorithm|Equation|Eq\.)\s+(\d+(?:\.\d+)?)\b", re.IGNORECASE)

    for u in units:
        if u.normalized_role in {"references"}:
            continue
        lines_and_sents = re.split(r"(?<=[.!?])\s+|\n", u.content)
        for seg in lines_and_sents:
            s_clean = re.sub(r"\s+", " ", seg).strip()
            if len(s_clean) < 8 or re.search(r"\.{4,}", s_clean):
                continue
            for m in ref_pat.finditer(s_clean):
                raw_kind = m.group(1).lower().rstrip(".")
                num = m.group(2)
                if raw_kind in {"fig"}:
                    kind = "figure"
                    label = f"Figure {num}"
                elif raw_kind in {"eq"}:
                    kind = "equation"
                    label = f"Equation {num}"
                elif raw_kind == "figure":
                    kind = "figure"
                    label = f"Figure {num}"
                elif raw_kind == "table":
                    kind = "table"
                    label = f"Table {num}"
                elif raw_kind == "algorithm":
                    kind = "algorithm"
                    label = f"Algorithm {num}"
                else:
                    kind = "equation"
                    label = f"Equation {num}"

                key = (label.lower(), u.page)
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    {
                        "id": f"tf-{len(items) + 1}",
                        "label": label,
                        "kind": kind,
                        "page": int(u.page or 1),
                        "chunk_id": u.chunk_id,
                        "section": u.section_title,
                        "caption_or_context": s_clean[:200],
                        "visually_parsed": False,
                    }
                )
                if len(items) >= 30:
                    break
            if len(items) >= 30:
                break
        if len(items) >= 30:
            break

    return {
        "items": items,
        "visual_parsing_limitation": (
            "Table/figure references are extracted from document text and captions only; "
            "embedded chart imagery and visual grid structures are not parsed directly in Phase 1."
        ),
    }


def _extract_section_fields_deterministic(
    units: List[ChunkUnit],
    tracker: EvidenceTracker,
    numerical_data: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    def _build_from_hits(hits: List[Tuple[ChunkUnit, str]], fact_type: str = "explicit", conf: float = 0.85) -> Dict[str, Any]:
        if not hits:
            return missing_field()
        primary_u, primary_sent = hits[0]
        extras = [(u, extract_verbatim_excerpt(u.content, s), conf - 0.03) for u, s in hits[1:]]
        summary_val = " ".join(s for _, s in hits)[:520]
        return tracker.make_field(
            value=summary_val,
            unit=primary_u,
            fact_type=fact_type,
            confidence=conf,
            excerpt_override=primary_sent[:230],
            additional_units=extras,
        )

    # Research Context
    rc_specs = {
        "problem_statement": ([r"\bproblem\b", r"\bchallenge\b", r"\bdifficult\b", r"\bvulnerability\b", r"\baddressed\b", r"\bsecurity\s+threats?\b"], {"abstract", "introduction", "front_matter"}),
        "motivation": ([r"\bmotivat", r"\bneed\s+for\b", r"\bincreasingly\b", r"\bcritical\b", r"\bgrowing\s+demand\b"], {"abstract", "introduction"}),
        "research_objective": ([r"\bobjective\b", r"\baim(?:s|ed)?\b", r"\bpropose\b", r"\bwe\s+present\b", r"\bdesign\s+and\s+implement\b", r"\bfocuses?\s+on\b"], {"abstract", "introduction", "methodology"}),
        "research_questions": ([r"\bresearch\s+question", r"\brq\d", r"\bwe\s+investigate\s+whether\b", r"\?\s*$"], {"introduction", "experiments"}),
        "hypothesis": ([r"\bhypothes", r"\bwe\s+hypothesize\b", r"\bexpected\s+that\b"], {"introduction", "methodology", "experiments"}),
    }
    research_context: Dict[str, Any] = {}
    for field_name, (kws, roles) in rc_specs.items():
        hits = _find_evidence_in_units(units, kws, roles, max_hits=2)
        research_context[field_name] = _build_from_hits(hits, fact_type="explicit", conf=0.84)

    # Research domain (check explicit keywords/title/abstract, or labeled inferred domain cue)
    domain_hits = _find_evidence_in_units(
        units,
        [r"\bcloud\s+security\b", r"\bdistributed\s+storage\b", r"\bmachine\s+learning\b", r"\bnatural\s+language\s+processing\b", r"\bcomputer\s+vision\b", r"\bcryptograph", r"\bencryption\b", r"\bcybersecurity\b", r"\bdeep\s+learning\b", r"\bkey\s+management\b"],
        {"abstract", "keywords", "introduction", "front_matter"},
        max_hits=1,
    )
    if domain_hits:
        u_dom, s_dom = domain_hits[0]
        research_context["research_domain"] = tracker.make_field(s_dom[:240], unit=u_dom, fact_type="explicit", confidence=0.83)
    else:
        research_context["research_domain"] = missing_field()

    # Methodology
    meth_specs = {
        "methodology_type": ([r"\bexperimental\b", r"\bempirical\b", r"\bquantitative\b", r"\barchitecture\b", r"\btheoretical\b", r"\bhybrid\b", r"\bsystem\s+design\b"], {"abstract", "methodology", "experiments"}),
        "proposed_approach": ([r"\bwe\s+propose\b", r"\bproposed\s+(?:framework|approach|system|model|method|architecture|scheme)\b", r"\bcephvault\b", r"\bpipeline\b"], {"abstract", "introduction", "methodology"}),
        "algorithms_models": ([r"\b(?:aes|rsa|ecc|sha\-?256|bert|transformer|trocr|cnn|lstm|svm|random\s+forest|algorithm|homomorphic|cryptographic)\b"], {"abstract", "methodology", "experiments"}),
        "architecture": ([r"\barchitecture\b", r"\bmodules?\b", r"\bcomponent\b", r"\blayer\b", r"\bworkflow\b"], {"methodology", "experiments"}),
        "framework_tools": ([r"\b(?:pytorch|tensorflow|keras|scikit\-learn|ceph|openssl|kmip|vault|barbican|python|fastapi|docker|linux)\b"], {"methodology", "experiments"}),
        "dataset": ([r"\bdataset\b", r"\bcorpus\b", r"\bbenchmark\b", r"\bdata\s+is\s+gathered\b"], {"abstract", "methodology", "experiments"}),
        "dataset_size": ([r"\b\d[\d,]*(?:\.\d+)?\s*(?:[a-z\-]+\s+){0,2}(?:samples?|records?|images?|instances?|documents?|lines?|examples?|rows?|flows?)\b", r"\b\d[\d,]*(?:\.\d+)?\s*(?:mb|gb|tb)\s+(?:dataset|corpus|data)\b"], {"methodology", "experiments", "results"}),
        "preprocessing": ([r"\bpreprocess", r"\bnormaliz", r"\btokeniz", r"\bclean(?:ing|ed)\b", r"\baugment", r"\bbinariz"], {"methodology", "experiments"}),
        "experimental_setup": ([r"\bexperimental\s+setup\b", r"\btestbed\b", r"\bhardware\b", r"\bcluster\b", r"\bcpu\b", r"\bgpu\b", r"\bevaluation\s+environment\b", r"\bhyperparameter\b"], {"experiments", "methodology", "results"}),
    }
    methodology: Dict[str, Any] = {}
    for field_name, (kws, roles) in meth_specs.items():
        hits = _find_evidence_in_units(units, kws, roles, max_hits=2)
        methodology[field_name] = _build_from_hits(hits, fact_type="explicit", conf=0.85)

    # Evaluation
    eval_specs = {
        "evaluation_metrics": ([r"\baccuracy\b", r"\bprecision\b", r"\brecall\b", r"\bf1\b", r"\blatency\b", r"\bthroughput\b", r"\boverhead\b", r"\brobustness\b", r"\bmetric\b"], {"results", "experiments", "abstract"}),
        "baseline_methods": ([r"\bbaseline\b", r"\bcompared\s+(?:with|to|against)\b", r"\bexisting\s+(?:methods?|systems?|kms)\b", r"\btraditional\b"], {"results", "experiments", "related_work"}),
        "experiments": ([r"\bexperiment", r"\bbenchmark\b", r"\btest(?:ed|ing)\b", r"\bwe\s+evaluate\b"], {"experiments", "results"}),
        "results": ([r"\bresult", r"\bachiev", r"\bdemonstrate\b", r"\boutperform", r"\bfindings?\b", r"\bwe\s+show\b"], {"results", "abstract", "conclusion"}),
        "comparisons": ([r"\boutperform", r"\bfaster\s+than\b", r"\bbetter\s+than\b", r"\bversus\b", r"\bcomparison\b"], {"results", "experiments", "discussion"}),
    }
    evaluation: Dict[str, Any] = {}
    for field_name, (kws, roles) in eval_specs.items():
        hits = _find_evidence_in_units(units, kws, roles, max_hits=2)
        evaluation[field_name] = _build_from_hits(hits, fact_type="explicit", conf=0.85)

    if numerical_data:
        top_nums = [f"{n['metric_name']}: {n['original_value']} (p.{n['source']['page']})" for n in numerical_data[:6]]
        first_src = numerical_data[0]["source"]
        first_u = next((u for u in units if u.chunk_id == first_src.get("chunk_id") and u.page == first_src.get("page")), units[0])
        evaluation["numerical_findings"] = tracker.make_field(
            value="; ".join(top_nums),
            unit=first_u,
            fact_type="explicit",
            confidence=0.9,
            excerpt_override=first_src.get("excerpt", ""),
        )
    else:
        evaluation["numerical_findings"] = missing_field()

    # Conclusion
    concl_specs = {
        "main_conclusions": ([r"\bin\s+conclusion\b", r"\bconclude\b", r"\bsummar", r"\bthis\s+(?:paper|study|thesis)\s+(?:demonstrates|presents|concludes)\b"], {"conclusion", "abstract", "results"}),
        "limitations": ([r"\blimitation", r"\bdrawback", r"\bconstraint", r"\bthreat\s+to\s+validity\b", r"\bshortcoming\b", r"\bbottleneck\b"], {"discussion", "conclusion", "results"}),
        "future_work": ([r"\bfuture\s+work\b", r"\bfuture\s+research\b", r"\bwill\s+extend\b", r"\bfurther\s+work\b", r"\bnext\s+step\b", r"\bplan\s+to\b"], {"conclusion", "discussion"}),
    }
    conclusion: Dict[str, Any] = {}
    for field_name, (kws, roles) in concl_specs.items():
        hits = _find_evidence_in_units(units, kws, roles, max_hits=2)
        conclusion[field_name] = _build_from_hits(hits, fact_type="explicit", conf=0.84)

    return {
        "research_context": research_context,
        "methodology": methodology,
        "evaluation": evaluation,
        "conclusion": conclusion,
    }


def _select_bounded_evidence_packet(units: List[ChunkUnit], max_chars: int = 7000) -> str:
    """
    Build a section-balanced evidence packet for local Ollama without overflowing context
    windows on long theses/papers.
    """
    if not units:
        return ""

    role_buckets: Dict[str, List[ChunkUnit]] = {
        "front": [],
        "intro": [],
        "method": [],
        "results": [],
        "conclusion": [],
        "other": [],
    }
    for u in units:
        if u.page <= 2 or u.normalized_role in {"front_matter", "abstract", "keywords"}:
            role_buckets["front"].append(u)
        elif u.normalized_role in {"introduction", "related_work"}:
            role_buckets["intro"].append(u)
        elif u.normalized_role in {"methodology", "experiments"}:
            role_buckets["method"].append(u)
        elif u.normalized_role in {"results", "discussion"}:
            role_buckets["results"].append(u)
        elif u.normalized_role == "conclusion":
            role_buckets["conclusion"].append(u)
        elif u.normalized_role != "references":
            role_buckets["other"].append(u)

    selected: List[ChunkUnit] = []
    seen_idx: Set[int] = set()
    # Interleave across key structural roles (up to ~3 chunks per bucket)
    for bucket_name, quota in [("front", 3), ("intro", 2), ("method", 3), ("results", 3), ("conclusion", 2), ("other", 2)]:
        for u in role_buckets[bucket_name][:quota]:
            if u.chunk_index not in seen_idx:
                seen_idx.add(u.chunk_index)
                selected.append(u)

    selected.sort(key=lambda x: x.chunk_index)
    parts: List[str] = []
    total_len = 0
    for u in selected:
        cid_label = str(u.chunk_id) if u.chunk_id is not None else f"idx-{u.chunk_index}"
        snippet = re.sub(r"\s+", " ", u.content).strip()[:650]
        block = f"[CHUNK {cid_label} | Page {u.page} | Section: {u.section_title}]\n{snippet}\n"
        if total_len + len(block) > max_chars:
            break
        parts.append(block)
        total_len += len(block)

    return "\n".join(parts)


def _merge_ollama_structured_claims(
    ollama_data: Dict[str, Any],
    base_sections: Dict[str, Dict[str, Any]],
    tracker: EvidenceTracker,
) -> bool:
    """
    Validate Ollama's JSON output and merge ONLY claims that verify cleanly against real
    document chunks. Never introduces ungrounded claims or overwrites missing safeguards.
    Returns True if at least one structured section field was grounded from Ollama.
    """
    merged_any = False
    section_roles_map = {
        "research_context": {"abstract", "introduction", "front_matter"},
        "methodology": {"methodology", "experiments", "abstract"},
        "evaluation": {"results", "experiments", "discussion", "abstract"},
        "conclusion": {"conclusion", "discussion", "abstract"},
    }

    for sec_key, target_dict in [
        ("research_context", base_sections["research_context"]),
        ("methodology", base_sections["methodology"]),
        ("evaluation", base_sections["evaluation"]),
        ("conclusion", base_sections["conclusion"]),
        ("basic_information", base_sections.get("basic_information", {})),
    ]:
        llm_sec = ollama_data.get(sec_key)
        if not isinstance(llm_sec, dict) or not isinstance(target_dict, dict):
            continue

        for field_name, existing_field in list(target_dict.items()):
            raw_item = llm_sec.get(field_name)
            if isinstance(raw_item, dict):
                claim_val = str(raw_item.get("value") or "").strip()
                raw_cid = raw_item.get("chunk_id")
                fact_type = str(raw_item.get("fact_type") or "explicit").lower()
            elif isinstance(raw_item, str):
                claim_val = raw_item.strip()
                raw_cid = None
                fact_type = "explicit"
            else:
                continue

            if not claim_val or "not explicitly stated" in claim_val.lower() or len(claim_val) < 6:
                continue
            if fact_type not in {"explicit", "derived", "inferred"}:
                fact_type = "explicit"

            # Never let Ollama overwrite a high-confidence extracted title/abstract/numerical summary
            if sec_key == "basic_information" and existing_field.get("fact_type") != "missing":
                continue
            if field_name == "numerical_findings" and existing_field.get("fact_type") == "explicit":
                continue

            pref_cid: Optional[int] = None
            if isinstance(raw_cid, int):
                pref_cid = raw_cid
            elif isinstance(raw_cid, str) and raw_cid.isdigit():
                pref_cid = int(raw_cid)

            matched_unit, match_conf = tracker.find_best_unit(
                claim_val,
                preferred_chunk_id=pref_cid,
                preferred_roles=section_roles_map.get(sec_key),
                use_semantic_fallback=True,
            )
            if matched_unit is None:
                continue

            # Keep inferred claims strictly labeled and lower confidence than explicit text
            if fact_type == "inferred":
                match_conf = min(match_conf, 0.72)

            grounded = tracker.make_field(
                value=claim_val[:480],
                unit=matched_unit,
                fact_type=fact_type,
                confidence=match_conf,
            )
            if grounded.get("fact_type") != "missing":
                target_dict[field_name] = grounded
                merged_any = True

    return merged_any


def extract_structured_research_analysis(
    document_id: int,
    units: List[ChunkUnit],
    sections: List[Dict[str, Any]],
    skip_llm: bool = False,
) -> Dict[str, Any]:
    """
    Execute deterministic grounded extraction followed by bounded local Ollama refinement
    with automatic fallback if Ollama is unreachable, slow, or returns invalid JSON.
    """
    t0 = time.perf_counter()
    tracker = EvidenceTracker(document_id=document_id, units=units)

    basic_info = _extract_basic_information(units, tracker)
    numerical_data = _extract_numerical_data(units, tracker)
    tables_and_figures = _extract_tables_and_figures(units)
    det_sections = _extract_section_fields_deterministic(units, tracker, numerical_data)

    det_sections["basic_information"] = basic_info
    extraction_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    llm_ms = 0.0
    analysis_mode = "deterministic_fallback"

    if not skip_llm and units:
        evidence_packet = _select_bounded_evidence_packet(units)
        if evidence_packet:
            prompt = f"""You are a precise academic information extraction engine.
Read ONLY the provided document evidence chunks. Do NOT invent or assume anything not present in the chunks.
If a field is not supported by the evidence, set its "value" to "{MISSING_FIELD_TEXT}".
Classify each populated field as "explicit" (directly stated) or "inferred" (minimal high-level classification such as broad domain). Do not present inference as explicit fact.
For every populated field, include the supporting integer chunk_id from the chunk header "[CHUNK <id> | ...]".

Return valid JSON matching this exact top-level structure:
{{
  "basic_information": {{
    "title": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "authors": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}}
  }},
  "research_context": {{
    "research_domain": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "problem_statement": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "motivation": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "research_objective": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "research_questions": {{"value": "{MISSING_FIELD_TEXT}", "chunk_id": null, "fact_type": "explicit"}},
    "hypothesis": {{"value": "{MISSING_FIELD_TEXT}", "chunk_id": null, "fact_type": "explicit"}}
  }},
  "methodology": {{
    "methodology_type": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "proposed_approach": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "algorithms_models": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "architecture": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "framework_tools": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "dataset": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "dataset_size": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "preprocessing": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "experimental_setup": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}}
  }},
  "evaluation": {{
    "evaluation_metrics": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "baseline_methods": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "experiments": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "results": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "comparisons": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}}
  }},
  "conclusion": {{
    "main_conclusions": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "limitations": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}},
    "future_work": {{"value": "...", "chunk_id": 1, "fact_type": "explicit"}}
  }}
}}

DOCUMENT EVIDENCE CHUNKS:
{evidence_packet}
"""
            t_llm = time.perf_counter()
            try:
                ollama_json = query_ollama_json(
                    prompt=prompt,
                    system_prompt="Extract strictly factual, chunk-grounded academic metadata as valid JSON.",
                    temperature=0.1,
                    timeout=35,
                )
                if isinstance(ollama_json, dict):
                    merged = _merge_ollama_structured_claims(ollama_json, det_sections, tracker)
                    if merged:
                        analysis_mode = "ollama_hybrid"
            except (OllamaError, ValueError, Exception) as exc:
                logger.info("Research analyzer falling back to deterministic extraction: %s", exc)
            finally:
                llm_ms = round((time.perf_counter() - t_llm) * 1000.0, 2)

    # Compute factual evidence coverage ratio across populated fields
    all_fields = []
    for sec_key in ("basic_information", "research_context", "methodology", "evaluation", "conclusion"):
        all_fields.extend(det_sections[sec_key].values())
    populated = [f for f in all_fields if f.get("fact_type") != "missing"]
    grounded = [f for f in populated if len(f.get("sources") or []) > 0]
    evidence_coverage = round(len(grounded) / len(populated), 2) if populated else 0.0

    return {
        "analysis_mode": analysis_mode,
        "basic_information": basic_info,
        "research_context": det_sections["research_context"],
        "methodology": det_sections["methodology"],
        "evaluation": det_sections["evaluation"],
        "conclusion": det_sections["conclusion"],
        "numerical_data": numerical_data,
        "tables_and_figures": tables_and_figures,
        "evidence": tracker.evidence_map,
        "evidence_coverage": evidence_coverage,
        "extraction_ms": extraction_ms,
        "llm_ms": llm_ms,
    }

