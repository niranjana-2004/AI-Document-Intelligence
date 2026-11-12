from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.research.paper_section_service import ChunkUnit

CORE_ACADEMIC_ROLES = {
    "abstract",
    "introduction",
    "related_work",
    "methodology",
    "experiments",
    "results",
    "discussion",
    "conclusion",
    "references",
}

_RESUME_OR_NON_ACADEMIC_MARKERS = [
    r"\bcareer\s+aspiration\b",
    r"\beducational\s+qualifications\b",
    r"\binternships?\s+done\b",
    r"\bcurriculum\s+vitae\b",
    r"\blinkedin\.com/in/\b",
    r"\blanguages?\s+known\b",
    r"\bpersonal\s+details\b",
    r"\binvoice\s+number\b",
    r"\bsubtotal\b.*\btotal\b",
]


def detect_research_paper(
    units: List[ChunkUnit],
    sections: List[Dict[str, Any]],
    full_text: str,
    manual_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Determine whether a document is likely an academic/research paper strictly using
    document content evidence (sections, citation patterns, venue/DOI/thesis cues,
    table/figure density, and domain signals) — never relying on filename alone.
    """
    text = full_text or ""
    text_lower = text.lower()
    char_len = len(text.strip())

    signals: List[str] = []
    missing_signals: List[str] = []
    score = 0.0

    if char_len < 160:
        is_paper = manual_override == "research_paper"
        return {
            "is_research_paper": is_paper,
            "confidence": 0.08 if not is_paper else 0.5,
            "classification": "research_paper" if is_paper else "non_research",
            "manual_override": manual_override if manual_override in {"research_paper", "non_research"} else None,
            "signals": [],
            "missing_signals": ["sufficient_text_length", "abstract", "methodology", "results", "references"],
            "rationale": (
                "Manually classified as a research paper by user."
                if is_paper
                else "Document contains insufficient text (<250 characters) to confirm research paper structure."
            ),
        }

    # Flatten roles from detected section hierarchy
    detected_roles: set[str] = set()

    def _collect_roles(nodes: List[Dict[str, Any]]) -> None:
        for n in nodes:
            detected_roles.add(n.get("normalized_role", "other"))
            _collect_roles(n.get("children", []))

    _collect_roles(sections)

    # Also inspect explicit inline markers across first 8k + last 8k chars
    head_tail_lower = (text[:8000] + "\n" + text[-8000:]).lower()

    has_abstract = "abstract" in detected_roles or bool(re.search(r"(?:^|\n)\s*abstract\b[:\s—\-]*\n?", text[:6000], re.I))
    has_keywords = "keywords" in detected_roles or bool(re.search(r"\b(?:keywords?|index\s+terms?)\s*[:—]", text[:6000], re.I))
    has_intro = "introduction" in detected_roles
    has_related = "related_work" in detected_roles or bool(re.search(r"\b(?:related\s+work|literature\s+review)\b", head_tail_lower))
    has_method = "methodology" in detected_roles or bool(re.search(r"\b(?:methodology|proposed\s+(?:framework|method|system|architecture)|materials\s+and\s+methods)\b", text_lower))
    has_experiments = "experiments" in detected_roles or bool(re.search(r"\b(?:experimental\s+setup|dataset|training\s+details|hyperparameters?)\b", text_lower))
    has_results = "results" in detected_roles or bool(re.search(r"\b(?:results?\s+and\s+discussion|performance\s+analysis|empirical\s+evaluation)\b", text_lower))
    has_conclusion = "conclusion" in detected_roles or bool(re.search(r"(?:^|\n)\s*(?:\d+\.?\s+)?conclusions?\b", text_lower))
    has_references = "references" in detected_roles or bool(re.search(r"(?:^|\n)\s*(?:\d+\.?\s+)?(?:references|bibliography|works\s+cited)\b", text[-20000:], re.I))

    if has_abstract:
        signals.append("abstract")
        score += 0.22
    else:
        missing_signals.append("abstract")

    if has_keywords:
        signals.append("keywords")
        score += 0.07

    if has_intro:
        signals.append("introduction")
        score += 0.09
    else:
        missing_signals.append("introduction")

    if has_related:
        signals.append("related_work")
        score += 0.08

    if has_method:
        signals.append("methodology")
        score += 0.14
    else:
        missing_signals.append("methodology")

    if has_experiments:
        signals.append("experiments")
        score += 0.08

    if has_results:
        signals.append("results")
        score += 0.12
    else:
        missing_signals.append("results")

    if has_conclusion:
        signals.append("conclusion")
        score += 0.07

    if has_references:
        signals.append("references")
        score += 0.13
    else:
        missing_signals.append("references")

    # Citation patterns: [1], [12, 13], (Author et al., 2024), et al.
    bracket_cites = len(re.findall(r"\[\d{1,3}(?:\s*,\s*\d{1,3})*\]", text))
    author_year_cites = len(re.findall(r"\([A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?,\s*(?:19|20)\d{2}\)", text))
    et_al_hits = len(re.findall(r"\bet\s+al\.", text))
    total_cites = bracket_cites + author_year_cites + et_al_hits
    if total_cites >= 5:
        signals.append("citation_density")
        score += 0.12
    elif total_cites >= 2:
        signals.append("citations_present")
        score += 0.05

    # Academic venue / thesis / DOI / ISSN / arXiv metadata
    pub_cues = bool(
        re.search(
            r"\b(?:doi:|issn\b|isbn\b|arxiv:|ieee\b|acm\b|springer\b|journal\s+of\b|proceedings\s+of\b|to\s+cite\s+this\s+article|a\s+thesis\s+submitted|master\s+of\s+(?:computer\s+)?science)\b",
            text[:6500],
            re.IGNORECASE,
        )
    )
    if pub_cues:
        signals.append("publication_or_thesis_metadata")
        score += 0.14

    # Table / Figure / Equation references
    fig_tab_count = len(re.findall(r"\b(?:Table|Figure|Fig\.|Algorithm|Equation)\s+\d+", text))
    if fig_tab_count >= 2:
        signals.append("tables_or_figures")
        score += 0.07
    elif fig_tab_count >= 1:
        signals.append("tables_or_figures")
        score += 0.04

    # Author / affiliation pattern near top of document
    email_top = bool(re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text[:2500]))
    if email_top and (pub_cues or has_abstract):
        signals.append("author_affiliation_block")
        score += 0.05

    # Counter-signals for resumes / CVs / invoices / non-academic prose
    resume_hits = sum(1 for pat in _RESUME_OR_NON_ACADEMIC_MARKERS if re.search(pat, text_lower))
    if resume_hits >= 2:
        score -= 0.45

    if len(units) <= 2 and not has_abstract and not has_references and total_cites == 0:
        score = min(score, 0.42)

    confidence = round(max(0.02, min(0.99, score)), 2)

    if confidence >= 0.62:
        classification = "research_paper"
        is_research = True
    elif confidence >= 0.35:
        classification = "borderline_technical"
        is_research = False
    else:
        classification = "non_research"
        is_research = False

    clean_override: Optional[str] = None
    if manual_override in {"research_paper", "non_research"}:
        clean_override = manual_override
        is_research = manual_override == "research_paper"
        classification = "research_paper" if is_research else "non_research"

    if clean_override == "research_paper":
        rationale = f"Manually classified as a research paper (automatic content score {int(confidence * 100)}%)."
    elif clean_override == "non_research":
        rationale = f"Manually classified as non-research document (automatic content score {int(confidence * 100)}%)."
    elif is_research:
        rationale = f"Strong academic structure detected ({len(signals)} content signals including {', '.join(signals[:4])})."
    elif classification == "borderline_technical":
        rationale = (
            "Technical document shares partial structural cues (such as numbered sections or quantitative setup) "
            f"but lacks full academic conventions ({', '.join(missing_signals[:3]) or 'abstract/references'}). "
            "You can manually classify it as a research paper if desired."
        )
    else:
        rationale = "Content lacks academic paper indicators (abstract, methodology, citations, references)."

    return {
        "is_research_paper": is_research,
        "confidence": confidence,
        "classification": classification,
        "manual_override": clean_override,
        "signals": signals,
        "missing_signals": missing_signals,
        "rationale": rationale,
    }

