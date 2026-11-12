from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.schemas.research_paper import MISSING_FIELD_TEXT
from app.services.embedding_services import generate_embedding
from app.services.research.paper_section_service import ChunkUnit
from app.services.similarity_service import cosine_similarity

_STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "using", "based",
    "paper", "study", "authors", "propose", "proposed", "approach", "method", "system",
    "results", "show", "states", "stated", "which", "their", "while", "where", "were",
    "was", "are", "have", "has", "been", "being", "than", "also", "more", "most",
}


def _tokenize_significant(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9.\-%]{1,}", (text or "").lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) >= 2}


def _parse_embedding(raw: Any) -> Optional[List[float]]:
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else None
        except Exception:
            return None
    return None


def extract_verbatim_excerpt(chunk_text: str, anchor_text: str, max_len: int = 230) -> str:
    """
    Extract a clean, verbatim short excerpt around the best matching sentence/phrase in a chunk.
    """
    clean_chunk = re.sub(r"\s+", " ", (chunk_text or "")).strip()
    if not clean_chunk:
        return ""
    if len(clean_chunk) <= max_len:
        return clean_chunk

    sentences = re.split(r"(?<=[.!?])\s+", clean_chunk)
    anchor_tokens = _tokenize_significant(anchor_text)
    anchor_nums = set(re.findall(r"\d+(?:\.\d+)?%?", anchor_text or ""))

    best_sent = sentences[0]
    best_score = -1.0
    for sent in sentences:
        if len(sent.strip()) < 15:
            continue
        s_tokens = _tokenize_significant(sent)
        overlap = len(anchor_tokens & s_tokens)
        num_overlap = sum(2.5 for n in anchor_nums if n in sent)
        score = overlap + num_overlap
        if score > best_score:
            best_score = score
            best_sent = sent.strip()

    if len(best_sent) <= max_len:
        return best_sent
    return best_sent[: max_len - 3].rstrip() + "..."


def detect_figure_or_table_in_text(text: str) -> Optional[str]:
    match = re.search(
        r"\b(Table|Figure|Fig\.|Algorithm|Equation|Eq\.)\s+(\(\d+[a-z]?\)|\d+(?:\.\d+)?(?:\([a-z0-9]+\))?|[IVX]{1,5}\b)",
        text or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    kind_token = match.group(1)
    num_token = match.group(2)
    # Require uppercase Roman numeral if non-digit (avoid matching lowercase prose like "table in")
    if re.fullmatch(r"[ivx]+", num_token, re.IGNORECASE) and not re.fullmatch(r"[IVX]{1,5}", num_token):
        return None
    kind_low = kind_token.lower().rstrip(".")
    if kind_low in {"fig", "figure"}:
        canon_kind = "Figure"
    elif kind_low in {"eq", "equation"}:
        canon_kind = "Equation"
    elif kind_low == "table":
        canon_kind = "Table"
    else:
        canon_kind = "Algorithm"
    if canon_kind == "Equation" and not num_token.startswith("("):
        clean_num = num_token
    else:
        clean_num = num_token
    return f"{canon_kind} {clean_num}"


class EvidenceTracker:
    """
    Maintains a deduplicated, sequentially indexed dictionary of verified EvidenceItems
    for a single research paper analysis run.
    """

    def __init__(self, document_id: int, units: List[ChunkUnit]):
        self.document_id = document_id
        self.units = units
        self._unit_by_chunk_id: Dict[int, ChunkUnit] = {
            u.chunk_id: u for u in units if u.chunk_id is not None
        }
        self._evidence: Dict[str, Dict[str, Any]] = {}
        self._dedup_map: Dict[Tuple[Optional[int], int, str], str] = {}

    @property
    def evidence_map(self) -> Dict[str, Dict[str, Any]]:
        return self._evidence

    def find_best_unit(
        self,
        claim_text: str,
        preferred_chunk_id: Optional[int] = None,
        preferred_roles: Optional[Iterable[str]] = None,
        use_semantic_fallback: bool = True,
    ) -> Tuple[Optional[ChunkUnit], float]:
        if not self.units or not (claim_text or "").strip():
            return None, 0.0

        claim_tokens = _tokenize_significant(claim_text)
        claim_nums = set(re.findall(r"\d+(?:\.\d+)?", claim_text))

        if preferred_chunk_id is not None and preferred_chunk_id in self._unit_by_chunk_id:
            pref_unit = self._unit_by_chunk_id[preferred_chunk_id]
            pref_tokens = _tokenize_significant(pref_unit.content)
            overlap = len(claim_tokens & pref_tokens)
            denom = max(1, min(len(claim_tokens), 8))
            lex_ratio = overlap / denom
            if lex_ratio >= 0.28 or any(n in pref_unit.content for n in claim_nums):
                return pref_unit, round(min(0.96, 0.72 + lex_ratio * 0.24), 2)

        role_set = set(preferred_roles) if preferred_roles else None
        best_unit: Optional[ChunkUnit] = None
        best_score = 0.0

        for u in self.units:
            u_tokens = _tokenize_significant(u.content)
            if not claim_tokens:
                continue
            overlap = len(claim_tokens & u_tokens)
            denom = max(1, min(len(claim_tokens), 9))
            score = overlap / denom
            if claim_nums:
                num_hits = sum(1 for n in claim_nums if re.search(rf"(?<!\d){re.escape(n)}(?!\d)", u.content))
                if num_hits:
                    score += 0.25 * (num_hits / len(claim_nums))
            if role_set and u.normalized_role in role_set:
                score += 0.08
            if score > best_score:
                best_score = score
                best_unit = u

        if best_unit is not None and best_score >= 0.34:
            return best_unit, round(min(0.95, 0.62 + best_score * 0.30), 2)

        if use_semantic_fallback and len(self.units) <= 180:
            try:
                q_emb = generate_embedding(claim_text[:400])
                best_sim = 0.0
                best_sem_unit: Optional[ChunkUnit] = None
                for u in self.units:
                    emb = _parse_embedding(u.embedding)
                    if not emb:
                        continue
                    sim = cosine_similarity(q_emb, emb)
                    if role_set and u.normalized_role in role_set:
                        sim += 0.04
                    if sim > best_sim:
                        best_sim = sim
                        best_sem_unit = u
                if best_sem_unit is not None and best_sim >= 0.42:
                    return best_sem_unit, round(min(0.90, 0.55 + (best_sim - 0.35) * 0.6), 2)
            except Exception:
                pass

        return None, 0.0

    def register_evidence(
        self,
        claim: str,
        unit: ChunkUnit,
        fact_type: str = "explicit",
        confidence: float = 0.90,
        excerpt_override: Optional[str] = None,
        figure_or_table: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        excerpt = (
            excerpt_override.strip()
            if excerpt_override and excerpt_override.strip()
            else extract_verbatim_excerpt(unit.content, claim)
        )
        fig_tab = figure_or_table or detect_figure_or_table_in_text(excerpt) or detect_figure_or_table_in_text(claim)
        dedup_key = (unit.chunk_id, unit.page, excerpt[:80].lower())
        existing_id = self._dedup_map.get(dedup_key)
        if existing_id and self._evidence[existing_id]["claim"] == claim:
            return existing_id, self._evidence[existing_id]["source"]

        ev_id = f"ev-{len(self._evidence) + 1}"
        source_dict = {
            "document_id": self.document_id,
            "page": int(unit.page or 1),
            "section": unit.section_title,
            "chunk_id": unit.chunk_id,
            "figure_or_table": fig_tab,
            "excerpt": excerpt,
            "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        }
        self._evidence[ev_id] = {
            "id": ev_id,
            "claim": claim,
            "fact_type": fact_type,
            "source": source_dict,
            "confidence": source_dict["confidence"],
        }
        self._dedup_map[dedup_key] = ev_id
        return ev_id, source_dict

    def make_field(
        self,
        value: str,
        unit: Optional[ChunkUnit] = None,
        fact_type: str = "explicit",
        confidence: float = 0.90,
        excerpt_override: Optional[str] = None,
        figure_or_table: Optional[str] = None,
        additional_units: Optional[List[Tuple[ChunkUnit, str, float]]] = None,
    ) -> Dict[str, Any]:
        cleaned_val = (value or "").strip()
        if not cleaned_val or cleaned_val.lower() in {
            "not explicitly stated",
            "not explicitly stated.",
            "not explicitly stated in the paper.",
            "not mentioned",
            "n/a",
            "none",
            "unknown",
        }:
            return {
                "value": MISSING_FIELD_TEXT,
                "fact_type": "missing",
                "confidence": 0.0,
                "evidence_ids": [],
                "sources": [],
            }

        evidence_ids: List[str] = []
        sources: List[Dict[str, Any]] = []

        if unit is not None:
            ev_id, src = self.register_evidence(
                claim=cleaned_val,
                unit=unit,
                fact_type=fact_type,
                confidence=confidence,
                excerpt_override=excerpt_override,
                figure_or_table=figure_or_table,
            )
            evidence_ids.append(ev_id)
            sources.append(src)

        if additional_units:
            for extra_unit, extra_excerpt, extra_conf in additional_units:
                if len(sources) >= 3:
                    break
                ev_id, src = self.register_evidence(
                    claim=cleaned_val,
                    unit=extra_unit,
                    fact_type=fact_type,
                    confidence=extra_conf,
                    excerpt_override=extra_excerpt,
                )
                if ev_id not in evidence_ids:
                    evidence_ids.append(ev_id)
                    sources.append(src)

        if not sources:
            # Never store unsupported claims as verified explicit facts
            return {
                "value": MISSING_FIELD_TEXT,
                "fact_type": "missing",
                "confidence": 0.0,
                "evidence_ids": [],
                "sources": [],
            }

        return {
            "value": cleaned_val,
            "fact_type": fact_type,
            "confidence": round(max(s["confidence"] for s in sources), 2),
            "evidence_ids": evidence_ids,
            "sources": sources,
        }


def missing_field() -> Dict[str, Any]:
    return {
        "value": MISSING_FIELD_TEXT,
        "fact_type": "missing",
        "confidence": 0.0,
        "evidence_ids": [],
        "sources": [],
    }

