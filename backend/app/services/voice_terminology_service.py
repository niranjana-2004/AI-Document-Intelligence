from collections import Counter, OrderedDict
from dataclasses import dataclass, field
import hashlib
import logging
import re
import threading
from typing import Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_mind_map import DocumentMindMap
from app.models.handwritten_analysis import HandwrittenConcept
from app.services.handwriting.handwritten_source_service import (
    get_document_transcription_source,
)
from app.services.handwriting.terminology_service import DOMAIN_VOCABULARIES
from app.services.search_service import ENGLISH_STOP_WORDS, clean_document_title

logger = logging.getLogger(__name__)

MAX_DOC_VOCAB_CACHE_ENTRIES = 256
MAX_SCOPED_BUNDLE_CACHE_ENTRIES = 64
_vocab_cache_lock = threading.Lock()
_doc_vocab_cache: OrderedDict[tuple[int, str], "DocumentVocabularyProfile"] = OrderedDict()
_scoped_bundle_cache: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()

IGNORED_UPPER_STOPWORDS = set(ENGLISH_STOP_WORDS) | {
    "all", "not", "are", "was", "but", "has", "had", "news", "plot", "item",
    "part", "page", "note", "way", "see", "end", "out", "new", "old", "now",
    "one", "two", "may", "can", "per", "etc", "via",
}

# Common lowercase English vocabulary safeguarded from accidental acronym rewriting
# unless strong neighboring context/colocation in selected documents overrides.
ORDINARY_ENGLISH_WORDS: set[str] = set(ENGLISH_STOP_WORDS) | {
    "able", "about", "above", "accept", "access", "act", "action", "add", "after",
    "again", "air", "all", "allow", "also", "always", "among", "amount", "and",
    "answer", "any", "apply", "area", "are", "art", "ask", "attack", "auto",
    "back", "bad", "bag", "ban", "band", "bar", "base", "basic", "bat", "bay",
    "bed", "before", "begin", "best", "better", "big", "bit", "block", "blue",
    "board", "body", "book", "both", "box", "boy", "break", "bring", "build",
    "bus", "but", "buy", "call", "can", "cap", "car", "card", "care", "case",
    "cat", "cause", "cell", "center", "change", "check", "child", "choice",
    "city", "class", "clean", "clear", "close", "cloud", "code", "cold", "color",
    "come", "common", "compare", "concept", "connect", "content", "control",
    "copy", "core", "cost", "could", "count", "course", "cover", "create",
    "cross", "cup", "cut", "dark", "data", "date", "day", "dead", "deal", "deep",
    "define", "describe", "design", "detail", "device", "did", "die", "diff",
    "different", "direct", "does", "dog", "done", "door", "dot", "down", "draw",
    "dream", "drive", "drop", "dry", "due", "ear", "early", "earth", "east",
    "easy", "eat", "edge", "edit", "effect", "egg", "eight", "end", "energy",
    "enough", "enter", "equal", "error", "even", "ever", "every", "example",
    "explain", "eye", "face", "fact", "fail", "fall", "false", "family", "fan",
    "far", "fast", "fat", "father", "fear", "feed", "feel", "few", "field",
    "fifth", "fig", "fight", "file", "fill", "film", "final", "find", "fine",
    "fire", "first", "fit", "five", "fix", "flag", "flat", "flood", "flow",
    "fly", "focus", "follow", "food", "foot", "for", "force", "form", "format",
    "forward", "four", "fourth", "free", "fresh", "friend", "from", "front",
    "full", "fun", "function", "future", "game", "gap", "gas", "gate", "gave",
    "general", "get", "girl", "give", "glass", "goal", "god", "gold", "good",
    "got", "graph", "gray", "great", "green", "ground", "group", "grow", "guess",
    "guide", "gun", "guy", "had", "hair", "half", "hall", "hand", "hang",
    "happen", "happy", "hard", "harm", "hat", "hate", "have", "head", "health",
    "hear", "heart", "heat", "heavy", "help", "her", "here", "hide", "high",
    "hill", "him", "his", "hit", "hold", "hole", "home", "hope", "horse", "hot",
    "hour", "house", "how", "huge", "human", "hundred", "hunt", "hurt", "ice",
    "idea", "identify", "idle", "ill", "image", "impact", "important", "include",
    "index", "info", "input", "inside", "instead", "into", "iron", "issue",
    "item", "its", "job", "join", "joy", "jump", "just", "keep", "kept", "key",
    "kick", "kid", "kill", "kind", "king", "knew", "know", "lab", "lack", "lady",
    "laid", "lake", "land", "language", "large", "last", "late", "later", "laugh",
    "law", "lay", "layer", "lead", "learn", "least", "leave", "led", "left",
    "leg", "less", "let", "letter", "level", "lie", "life", "lift", "light",
    "like", "limit", "line", "link", "lip", "list", "listen", "little", "live",
    "load", "local", "lock", "log", "long", "look", "loop", "lord", "lose",
    "loss", "lost", "lot", "loud", "love", "low", "luck", "lunch", "machine",
    "mad", "made", "main", "major", "make", "male", "man", "manage", "many",
    "map", "mark", "market", "mass", "match", "matter", "may", "maybe", "mean",
    "meaning", "measure", "media", "meet", "memory", "men", "mention", "message",
    "metal", "method", "middle", "might", "mile", "milk", "million", "mind",
    "mine", "minute", "miss", "mix", "mode", "model", "modern", "moment", "money",
    "month", "moon", "more", "morning", "most", "mother", "motion", "mount",
    "mouse", "mouth", "move", "much", "music", "must", "name", "narrow", "nation",
    "nature", "near", "neat", "neck", "need", "neither", "net", "network",
    "never", "new", "news", "next", "nice", "night", "nine", "none", "noon",
    "north", "nose", "not", "note", "notes", "nothing", "notice", "now",
    "number", "object", "obtain", "odd", "off", "offer", "office", "often",
    "oil", "old", "once", "one", "only", "onto", "open", "operate", "opinion",
    "option", "order", "ordinary", "other", "otherwise", "ought", "our", "out",
    "outside", "over", "own", "pack", "packet", "pad", "page", "pages", "paid",
    "pain", "paint", "pair", "pan", "paper", "parent", "park", "part", "pass",
    "past", "path", "pattern", "pay", "peace", "pen", "people", "per", "percent",
    "perfect", "perform", "period", "person", "phase", "phone", "photo", "phrase",
    "pick", "picture", "piece", "pig", "pile", "pin", "pipe", "place", "plain",
    "plan", "plane", "plant", "play", "please", "plot", "plug", "plus", "pocket",
    "poem", "point", "pole", "policy", "poll", "pool", "poor", "pop", "port",
    "post", "pot", "pound", "power", "practice", "present", "press", "pretty",
    "prevent", "price", "pride", "primary", "print", "prior", "private",
    "problem", "process", "produce", "product", "profile", "program", "project",
    "promise", "proof", "proper", "protect", "prove", "provide", "public",
    "pull", "pump", "pure", "purpose", "push", "put", "quality", "quarter",
    "queen", "question", "quick", "quiet", "quite", "quote", "race", "radio",
    "rail", "rain", "raise", "ran", "range", "rank", "rapid", "rare", "rate",
    "rather", "raw", "reach", "read", "ready", "real", "reason", "receive",
    "recent", "record", "red", "reduce", "refer", "region", "relate", "release",
    "remain", "remember", "remove", "rent", "repair", "repeat", "replace",
    "reply", "report", "request", "require", "research", "reserve", "reset",
    "resist", "resource", "respect", "respond", "response", "rest", "result",
    "return", "reveal", "review", "rice", "rich", "rid", "ride", "right", "ring",
    "rise", "risk", "river", "road", "rock", "role", "roll", "roof", "room",
    "root", "rope", "rose", "rough", "round", "route", "row", "rub", "rule",
    "run", "rush", "sad", "safe", "said", "sail", "sale", "salt", "same",
    "sample", "sand", "sat", "save", "saw", "say", "scale", "scan", "scene",
    "school", "science", "score", "screen", "sea", "search", "season", "seat",
    "second", "secret", "section", "security", "see", "seed", "seek", "seem",
    "seen", "select", "self", "sell", "send", "sense", "sent", "sentence",
    "separate", "series", "serious", "serve", "server", "service", "session",
    "set", "seven", "several", "sex", "shade", "shadow", "shake", "shall",
    "shape", "share", "sharp", "she", "sheet", "shell", "shift", "shine", "ship",
    "shirt", "shock", "shoe", "shoot", "shop", "short", "shot", "should",
    "shoulder", "show", "shut", "sick", "side", "sight", "sign", "signal",
    "silent", "silk", "silver", "similar", "simple", "simply", "sin", "since",
    "sing", "single", "sink", "sir", "sister", "sit", "site", "six", "size",
    "skill", "skin", "sky", "sleep", "slide", "slight", "slip", "slow", "small",
    "smart", "smell", "smile", "smoke", "smooth", "snow", "so", "soft", "soil",
    "solar", "sold", "sole", "solid", "solution", "solve", "some", "someone",
    "something", "sometimes", "son", "song", "soon", "sort", "sound", "source",
    "south", "space", "speak", "special", "specific", "speech", "speed", "spell",
    "spend", "spin", "spirit", "split", "spoke", "spoken", "sport", "spot",
    "spread", "spring", "square", "stable", "stack", "staff", "stage", "stand",
    "standard", "star", "start", "state", "statement", "station", "stay", "steady",
    "steal", "steam", "steel", "step", "stick", "still", "stock", "stone",
    "stood", "stop", "store", "storm", "story", "straight", "strange", "stream",
    "street", "strength", "stress", "stretch", "strict", "strike", "string",
    "strip", "strong", "structure", "student", "study", "stuff", "style",
    "subject", "submit", "such", "sudden", "suffer", "sugar", "suggest", "suit",
    "sum", "summary", "summer", "sun", "supply", "support", "suppose", "sure",
    "surface", "surprise", "sweet", "swim", "swing", "switch", "symbol",
    "system", "table", "tail", "take", "talk", "tall", "tank", "tap", "tape",
    "target", "task", "taste", "tax", "tea", "teach", "team", "tear", "tech",
    "technical", "tell", "ten", "tend", "term", "terms", "test", "text", "than",
    "thank", "that", "the", "their", "them", "theme", "then", "theory", "there",
    "these", "they", "thick", "thin", "thing", "think", "third", "this", "those",
    "though", "thought", "thousand", "thread", "three", "through", "throw",
    "thus", "tick", "tide", "tie", "tight", "till", "time", "tiny", "tip",
    "tire", "title", "today", "toe", "together", "told", "tone", "tongue",
    "tonight", "too", "took", "tool", "tools", "top", "topic", "total", "touch",
    "tough", "tour", "toward", "tower", "town", "toy", "track", "trade",
    "traffic", "train", "transfer", "travel", "treat", "tree", "trend", "trial",
    "trick", "tried", "trip", "trouble", "truck", "true", "trust", "truth",
    "try", "tube", "tune", "turn", "twelve", "twenty", "twice", "two", "type",
    "typical", "ugly", "under", "understand", "unit", "unite", "unless", "until",
    "up", "update", "upon", "upper", "urban", "urge", "us", "use", "used",
    "user", "usual", "valid", "valley", "value", "variety", "various", "vast",
    "verb", "verify", "version", "very", "vessel", "video", "view", "village",
    "visit", "visual", "voice", "volume", "vote", "wait", "wake", "walk", "wall",
    "want", "war", "warm", "warn", "was", "wash", "waste", "watch", "water",
    "wave", "way", "we", "weak", "wealth", "wear", "weather", "web", "week",
    "weight", "well", "went", "were", "west", "wet", "what", "wheel", "when",
    "where", "whether", "which", "while", "white", "who", "whole", "whom",
    "whose", "why", "wide", "wife", "wild", "will", "win", "wind", "window",
    "wine", "wing", "winter", "wire", "wise", "wish", "with", "within", "without",
    "woman", "women", "won", "wonder", "wood", "word", "words", "work", "world",
    "worry", "worse", "worst", "worth", "would", "wrap", "write", "written",
    "wrong", "wrote", "yard", "year", "yellow", "yes", "yet", "yield", "you",
    "young", "your", "zero", "zone",
    "extract", "extracted", "extraction", "handwritten", "handwriting",
    "encryption", "encrypt", "encrypted", "decrypt", "vault", "compute",
    "computed", "computing", "analyze", "analysis", "explain", "compare",
}

# Build domain lexicon index from existing terminology_service without hardcoding it as doc proof
_DOMAIN_UPPER_ACRONYMS: set[str] = set()
_DOMAIN_PHRASES_LOWER: set[str] = set()
_DOMAIN_COLOCATIONS: dict[str, set[str]] = {}
for _vocab in DOMAIN_VOCABULARIES.values():
    for _acr in _vocab.get("acronyms", ()):
        _DOMAIN_UPPER_ACRONYMS.add(str(_acr).upper())
        for _part in str(_acr).split():
            if len(_part) >= 2 and _part.isalpha():
                _DOMAIN_UPPER_ACRONYMS.add(_part.upper())
    for _ph in _vocab.get("phrases", ()):
        _DOMAIN_PHRASES_LOWER.add(str(_ph).lower())
    for _k, _vals in _vocab.get("context_colocations", {}).items():
        s = _DOMAIN_COLOCATIONS.setdefault(str(_k).lower(), set())
        for _v in _vals:
            s.add(str(_v).lower())


@dataclass
class DocumentVocabularyProfile:
    document_id: int
    filename: str
    document_title: str
    content_hash: str
    is_handwritten: bool
    total_tokens: int
    acronyms: dict[str, dict[str, Any]] = field(default_factory=dict)
    technical_terms: dict[str, dict[str, Any]] = field(default_factory=dict)
    phrases: dict[str, dict[str, Any]] = field(default_factory=dict)
    bigrams: Counter = field(default_factory=Counter)
    cooccurrence_map: dict[str, set[str]] = field(default_factory=dict)
    prefixed_numbers: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    lowercase_word_freq: Counter = field(default_factory=Counter)


def clear_voice_terminology_cache() -> None:
    """Clear the in-memory per-document and scoped voice terminology caches (for tests)."""
    with _vocab_cache_lock:
        _doc_vocab_cache.clear()
        _scoped_bundle_cache.clear()


def _extract_mind_map_labels(node: Any, out: list[str]) -> None:
    """Recursively collect node labels from a DocumentMindMap JSON tree."""
    if not isinstance(node, dict):
        return
    label = (node.get("label") or "").strip()
    if label:
        out.append(label)
    for child in node.get("children") or []:
        _extract_mind_map_labels(child, out)


def _gather_document_hash_and_texts(
    doc: Document,
    db: Session,
) -> tuple[str, list[str], list[str], list[str]]:
    """
    Gather canonical document text sections, headings/concept labels, and deterministic content hash.
    Reuses handwritten source service for handwritten docs so edited transcriptions take precedence
    and content hash invalidates automatically on edits.
    """
    section_texts: list[str] = []
    heading_labels: list[str] = []
    concept_labels: list[str] = []

    hash_parts: list[str] = [str(doc.filename or ""), str(doc.subject or "")]

    hw_page_texts: list[str] = []
    if doc.is_handwritten:
        try:
            hw_source = get_document_transcription_source(doc.id, db)
            hw_hash = hw_source.get("hash") or ""
            hw_full = (hw_source.get("full_text") or "").strip()
            hash_parts.append(f"hw:{hw_hash}")
            if hw_full:
                section_texts.append(hw_full)
                hw_page_texts = [
                    (p.get("text") or "").strip()
                    for p in hw_source.get("pages", [])
                    if (p.get("text") or "").strip()
                ]
        except Exception as err:
            logger.warning("Handwritten transcription source lookup failed for doc #%s: %s", doc.id, err)
            fallback_txt = (doc.extracted_text or "").strip()
            hash_parts.append(f"raw:{hashlib.sha256(fallback_txt.encode('utf-8')).hexdigest()}")
            if fallback_txt:
                section_texts.append(fallback_txt)
    else:
        doc_text = (doc.extracted_text or "").strip()
        hash_parts.append(f"txt:{hashlib.sha256(doc_text.encode('utf-8')).hexdigest()}")
        if doc_text:
            section_texts.append(doc_text)

    if hw_page_texts:
        # Canonical live handwritten pages (edited > raw) take precedence immediately even
        # before downstream embedding re-sync.
        chunk_texts = hw_page_texts
        chunk_hasher = hashlib.sha256()
        for ct in chunk_texts:
            chunk_hasher.update(ct.encode("utf-8"))
        hash_parts.append(f"chunks:{len(chunk_texts)}:{chunk_hasher.hexdigest()}")
    else:
        chunks = (
            db.query(DocumentChunk.content, DocumentChunk.category)
            .filter(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )
        chunk_texts = []
        chunk_hasher = hashlib.sha256()
        for c_text, _cat in chunks:
            if c_text and c_text.strip():
                ct = c_text.strip()
                chunk_texts.append(ct)
                chunk_hasher.update(ct.encode("utf-8"))
        hash_parts.append(f"chunks:{len(chunk_texts)}:{chunk_hasher.hexdigest()}")

        if not chunk_texts and section_texts:
            chunk_texts = [p.strip() for p in re.split(r"\n\s*\n", section_texts[0]) if p.strip()]
            if not chunk_texts:
                chunk_texts = [section_texts[0]]

    # Reuse stored HandwrittenConcept & DocumentMindMap terms only if hash matches current doc
    canonical_hash = hw_hash if doc.is_handwritten and "hw_hash" in locals() else None
    if doc.is_handwritten and canonical_hash:
        concepts = (
            db.query(HandwrittenConcept.name)
            .filter(
                HandwrittenConcept.document_id == doc.id,
                HandwrittenConcept.transcription_hash == canonical_hash,
            )
            .all()
        )
        for (cname,) in concepts:
            if cname and cname.strip():
                concept_labels.append(cname.strip())

    # Also check verified DocumentMindMap labels if cached for current document
    doc_text_for_mm = (doc.extracted_text or "").strip()
    mm_row = (
        db.query(DocumentMindMap)
        .filter(DocumentMindMap.document_id == doc.id)
        .order_by(DocumentMindMap.id.desc())
        .first()
    )
    if mm_row and isinstance(mm_row.mind_map_json, dict):
        expected_mm_hash = hashlib.sha256(doc_text_for_mm.encode("utf-8")).hexdigest() if doc_text_for_mm else ""
        if not mm_row.content_hash or mm_row.content_hash == expected_mm_hash or (canonical_hash and mm_row.content_hash == canonical_hash):
            _extract_mind_map_labels(mm_row.mind_map_json.get("root"), heading_labels)

    if doc.filename:
        heading_labels.append(clean_document_title(doc.filename))

    combined = "\n".join(hash_parts) + "|" + ",".join(sorted(concept_labels))
    content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    return content_hash, chunk_texts, heading_labels, concept_labels


def _extract_profile_for_document(
    doc: Document,
    content_hash: str,
    chunk_texts: list[str],
    heading_labels: list[str],
    concept_labels: list[str],
) -> DocumentVocabularyProfile:
    """Dynamically construct a rich vocabulary, colocation, and acronym profile from document evidence."""
    doc_title = clean_document_title(doc.filename)
    profile = DocumentVocabularyProfile(
        document_id=doc.id,
        filename=doc.filename or f"Document #{doc.id}",
        document_title=doc_title,
        content_hash=content_hash,
        is_handwritten=bool(doc.is_handwritten),
        total_tokens=0,
    )

    full_text = "\n\n".join(chunk_texts)

    # 1. Discover markdown / numbered / title-case headings from text
    discovered_headings = list(heading_labels)
    for line in full_text.splitlines():
        s = line.strip()
        if not s:
            continue
        m_md = re.match(r"^#{1,4}\s+(.+)$", s)
        if m_md:
            discovered_headings.append(m_md.group(1).strip())
            continue
        m_num = re.match(r"^(?:\d+(?:\.\d+)*[.)]?)\s+([A-Z][A-Za-z0-9\s\-/()]{2,65})$", s)
        if m_num:
            discovered_headings.append(m_num.group(1).strip())

    heading_upper_tokens: set[str] = set()
    heading_lower_phrases: set[str] = set()
    heading_words: set[str] = set()
    concept_upper_tokens: set[str] = set()
    concept_lower_phrases: set[str] = set()
    concept_words: set[str] = set()

    for h in discovered_headings:
        cleaned_h = re.sub(r"[#*:`]+", " ", h).strip()
        if len(cleaned_h) >= 3:
            heading_lower_phrases.add(cleaned_h.lower())
            heading_words.update(cleaned_h.lower().split())
            profile.phrases.setdefault(
                cleaned_h.lower(),
                {"canonical": cleaned_h, "freq": 0, "in_heading": True, "in_concept": False},
            )
            profile.phrases[cleaned_h.lower()]["freq"] += 1
            profile.phrases[cleaned_h.lower()]["in_heading"] = True
        for tok in re.findall(r"\b[A-Za-z][A-Za-z0-9\-]{1,24}\b", cleaned_h):
            if any(c.isupper() for c in tok) and len(re.sub(r"[^A-Za-z]", "", tok)) >= 2:
                if tok.isupper() or sum(1 for c in tok if c.isupper()) >= 2:
                    heading_upper_tokens.add(tok)
            if len(tok) >= 3 and tok.lower() not in ORDINARY_ENGLISH_WORDS:
                t_low = tok.lower()
                entry = profile.technical_terms.setdefault(
                    t_low,
                    {"canonical": tok, "freq": 0, "in_heading": True, "in_concept": False, "in_title": True},
                )
                entry["freq"] += 1
                entry["in_heading"] = True

    for c_label in concept_labels:
        cl = c_label.strip()
        if len(cl) >= 3:
            concept_lower_phrases.add(cl.lower())
            concept_words.update(cl.lower().split())
            ph_entry = profile.phrases.setdefault(
                cl.lower(),
                {"canonical": cl, "freq": 0, "in_heading": False, "in_concept": True},
            )
            ph_entry["freq"] += 1
            ph_entry["in_concept"] = True
        for tok in re.findall(r"\b[A-Za-z][A-Za-z0-9\-]{1,24}\b", cl):
            if any(c.isupper() for c in tok):
                if tok.isupper() or sum(1 for c in tok if c.isupper()) >= 2:
                    concept_upper_tokens.add(tok)
            if len(tok) >= 3 and tok.lower() not in ORDINARY_ENGLISH_WORDS:
                t_low = tok.lower()
                entry = profile.technical_terms.setdefault(
                    t_low,
                    {"canonical": tok, "freq": 0, "in_heading": False, "in_concept": True, "in_title": False},
                )
                entry["freq"] += 1
                entry["in_concept"] = True

    # 2. Parenthetical acronym definitions: e.g. "Transmission Control Block (TCB)"
    paren_defs: dict[str, str] = {}
    for m_def in re.finditer(r"\b([A-Za-z][A-Za-z0-9\s\-]{3,65}?)\s*\(([A-Za-z0-9\-]{2,10})\)", full_text):
        expansion = re.sub(r"\s+", " ", m_def.group(1)).strip()
        acr = m_def.group(2).strip()
        # Verify uppercase letters exist in parenthetical tag
        if sum(1 for ch in acr if ch.isupper()) >= 2:
            paren_defs[acr] = expansion
            # Record full expanded phrase
            exp_words = expansion.split()
            if 2 <= len(exp_words) <= 5:
                ph_entry = profile.phrases.setdefault(
                    expansion.lower(),
                    {"canonical": expansion, "freq": 0, "in_heading": False, "in_concept": True},
                )
                ph_entry["freq"] += 1

    # 3. Parenthetical comma-separated lists of acronyms: e.g. "(SYN, SYN-ACK, ACK)"
    list_acronyms: set[str] = set()
    for m_list in re.finditer(r"\(([A-Z][A-Za-z0-9\-]*(?:\s*,\s*[A-Z][A-Za-z0-9\-]*)+)\)", full_text):
        for item in m_list.group(1).split(","):
            it = item.strip()
            if 2 <= len(it) <= 12 and sum(1 for ch in it if ch.isupper()) >= 2:
                list_acronyms.add(it)

    # 4. Scan prefixed numeric standards/identifiers: e.g. "RFC 5961", "BCP 38", "AES-256", "SHA-256"
    for m_num in re.finditer(r"\b([A-Z]{2,8})[\s\-]?(\d{2,6})\b", full_text):
        prefix = m_num.group(1).upper()
        digits = m_num.group(2)
        sep = "-" if f"{prefix}-{digits}" in m_num.group(0) else " "
        full_code = f"{prefix}{sep}{digits}"
        lst = profile.prefixed_numbers.setdefault(prefix, [])
        existing = next((x for x in lst if x["number"] == digits), None)
        if existing:
            existing["freq"] += 1
        else:
            lst.append({"full": full_code, "number": digits, "freq": 1})

    # 5. Tokenize chunks to collect term frequencies, acronyms, bigrams, and chunk co-occurrence
    acronym_counts: Counter = Counter()
    acronym_canonicals: dict[str, str] = {}
    mixed_tech_counts: Counter = Counter()
    mixed_tech_canonicals: dict[str, str] = {}

    for chunk in chunk_texts:
        # Meaningful chunk vocabulary for co-occurrence support
        chunk_words = re.findall(r"\b[A-Za-z0-9][A-Za-z0-9\-]{1,28}\b", chunk)
        profile.total_tokens += len(chunk_words)
        meaningful_in_chunk: set[str] = set()

        for raw_w in chunk_words:
            low_w = raw_w.lower()
            if raw_w.islower() and raw_w.isalpha():
                profile.lowercase_word_freq[raw_w] += 1
            if low_w not in ENGLISH_STOP_WORDS and len(low_w) >= 2:
                meaningful_in_chunk.add(low_w)

            # Acronym candidate: >= 2 uppercase letters, length 2..8, e.g., SYN, TCP, DoS, DDoS, IPv6
            letters_only = re.sub(r"[^A-Za-z]", "", raw_w)
            upper_count = sum(1 for c in raw_w if c.isupper())
            if (
                2 <= len(raw_w) <= 8
                and upper_count >= 2
                and (raw_w.isupper() or raw_w in {"DoS", "DDoS", "IPv4", "IPv6", "PyAV", "TrOCR", "MiniLM", "LaTeX", "iOS", "macOS"} or (raw_w.endswith("s") and raw_w[:-1].isupper()))
            ):
                norm_acr = raw_w[:-1] if (len(raw_w) >= 3 and raw_w.endswith("s") and raw_w[:-1].isupper()) else raw_w
                key_up = norm_acr.upper()
                acronym_counts[key_up] += 1
                # Prefer pure uppercase canonical unless intentionally mixed like DoS/DDoS/TrOCR
                prev_can = acronym_canonicals.get(key_up)
                if not prev_can or norm_acr in {"DoS", "DDoS", "IPv4", "IPv6", "TrOCR", "MiniLM", "PyAV"}:
                    acronym_canonicals[key_up] = norm_acr

            # Hyphenated or CamelCase or OOV technical term
            if (
                "-" in raw_w
                or (sum(1 for c in raw_w if c.isupper()) >= 2 and len(raw_w) >= 4)
                or (len(letters_only) >= 4 and low_w not in ORDINARY_ENGLISH_WORDS)
            ):
                mixed_tech_counts[low_w] += 1
                if low_w not in mixed_tech_canonicals or (any(c.isupper() for c in raw_w) and not mixed_tech_canonicals[low_w].isupper()):
                    mixed_tech_canonicals[low_w] = raw_w

        # Sentence-aware bigrams (don't cross newline / sentence boundaries)
        for line in chunk.splitlines():
            sentences = re.split(r"[.!?;:\(\)]+", line)
            for sent in sentences:
                toks = re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", sent)
                for idx in range(len(toks) - 1):
                    w1 = toks[idx].lower()
                    w2 = toks[idx + 1].lower()
                    profile.bigrams[(w1, w2)] += 1
                    # Also track frequent domain/technical 2-word phrases
                    if w1 not in ENGLISH_STOP_WORDS or w2 not in ENGLISH_STOP_WORDS:
                        if profile.bigrams[(w1, w2)] >= 2 or f"{w1} {w2}" in _DOMAIN_PHRASES_LOWER:
                            phr = f"{toks[idx]} {toks[idx + 1]}"
                            phr_low = f"{w1} {w2}"
                            if phr_low not in profile.phrases:
                                profile.phrases[phr_low] = {
                                    "canonical": phr,
                                    "freq": profile.bigrams[(w1, w2)],
                                    "in_heading": False,
                                    "in_concept": False,
                                }
                            else:
                                profile.phrases[phr_low]["freq"] = max(
                                    profile.phrases[phr_low]["freq"],
                                    profile.bigrams[(w1, w2)],
                                )

        # Map terms occurring in this chunk to co-occurring chunk terms
        for term_low in meaningful_in_chunk:
            co = profile.cooccurrence_map.setdefault(term_low, set())
            co.update(meaningful_in_chunk)

    # Also ensure concept/heading/parenthetical acronyms register even if chunk OCR varied
    for tok in set(heading_upper_tokens) | set(concept_upper_tokens) | set(paren_defs.keys()) | list_acronyms:
        base_tok = tok.replace("-", "").upper() if "-" in tok and len(tok) <= 6 else tok.upper()
        if 2 <= len(tok) <= 8 and tok.upper() == tok or tok in {"DoS", "DDoS", "TrOCR", "MiniLM"}:
            key_up = tok.upper()
            acronym_counts[key_up] = max(acronym_counts[key_up], 1)
            acronym_canonicals.setdefault(key_up, tok)

    # 6. Populate final acronyms dict (filtering out single-occurrence handwritten OCR artifacts
    # unless attested by headings, concepts, parenthetical defs, list, domain vocab, or concise docs)
    is_concise_doc = profile.total_tokens < 300
    for key_up, freq in acronym_counts.items():
        canonical = acronym_canonicals.get(key_up, key_up)
        in_heading = canonical in heading_upper_tokens or key_up in heading_upper_tokens
        in_concept = canonical in concept_upper_tokens or key_up in concept_upper_tokens
        in_def = canonical in paren_defs or key_up in paren_defs or canonical in list_acronyms
        domain_match = key_up in _DOMAIN_UPPER_ACRONYMS

        # Filter obvious single-occurrence noisy artifacts in long documents unless attested
        if (
            freq < 2
            and not in_heading
            and not in_concept
            and not in_def
            and not domain_match
            and not is_concise_doc
        ):
            continue

        # Skip uppercase ordinary stopwords / Roman numerals (e.g., '(IN)', 'NEWS', 'II') unless domain/definition
        if (key_up.lower() in IGNORED_UPPER_STOPWORDS or key_up in {"II", "III", "IV", "VI", "VII", "VIII"}) and not domain_match and not in_def:
            continue

        profile.acronyms[key_up] = {
            "canonical": canonical,
            "freq": freq,
            "in_heading": in_heading,
            "in_definition": in_def,
            "in_concept": in_concept,
            "domain_match": domain_match,
            "expansion": paren_defs.get(canonical) or paren_defs.get(key_up),
        }

    # 7. Populate technical_terms dict
    title_words_set = set(doc_title.lower().split())
    for t_low, freq in mixed_tech_counts.items():
        if t_low in profile.technical_terms:
            profile.technical_terms[t_low]["freq"] = max(profile.technical_terms[t_low]["freq"], freq)
            continue
        canonical = mixed_tech_canonicals.get(t_low, t_low)
        in_heading = t_low in heading_words
        in_concept = t_low in concept_words
        in_domain = t_low.upper() in _DOMAIN_UPPER_ACRONYMS or t_low in _DOMAIN_COLOCATIONS
        # Skip sentence-initial capitalized ordinary words (e.g. 'Failed', 'Validate') that appear
        # in lowercase prose inside the document and are not CamelCase/acronym/heading/concept terms.
        upper_chars = sum(1 for ch in canonical if ch.isupper())
        if (
            upper_chars == 1
            and canonical[0].isupper()
            and "-" not in canonical
            and not in_heading
            and not in_concept
            and not in_domain
            and profile.lowercase_word_freq.get(t_low, 0) >= 1
        ):
            continue
        if freq >= 2 or in_heading or in_concept or in_domain or is_concise_doc or (
            not doc.is_handwritten and len(t_low) >= 4 and upper_chars >= 2
        ):
            profile.technical_terms[t_low] = {
                "canonical": canonical,
                "freq": freq,
                "in_heading": in_heading,
                "in_concept": in_concept,
                "in_title": t_low in title_words_set,
            }

    # Normalize single-capitalized heading terms back to lowercase whenever the document
    # actually uses that word predominantly in lowercase prose (e.g. 'Homomorphic' -> 'homomorphic'),
    # while keeping proper nouns ('Schrodinger', 'Faraday') and CamelCase ('CephVault').
    for t_low, t_meta in profile.technical_terms.items():
        can = t_meta.get("canonical") or t_low
        if (
            can
            and can[0].isupper()
            and not can.isupper()
            and sum(1 for ch in can if ch.isupper()) == 1
            and profile.lowercase_word_freq.get(t_low, 0) > 0
        ):
            t_meta["canonical"] = t_low

    return profile


def get_document_vocabulary_profile(doc: Document, db: Session) -> tuple[DocumentVocabularyProfile, bool]:
    """Retrieve cached DocumentVocabularyProfile if content hash matches, else rebuild & cache."""
    content_hash, chunk_texts, heading_labels, concept_labels = _gather_document_hash_and_texts(doc, db)
    cache_key = (doc.id, content_hash)

    with _vocab_cache_lock:
        cached = _doc_vocab_cache.get(cache_key)
        if cached is not None:
            _doc_vocab_cache.move_to_end(cache_key)
            return cached, True

    profile = _extract_profile_for_document(
        doc=doc,
        content_hash=content_hash,
        chunk_texts=chunk_texts,
        heading_labels=heading_labels,
        concept_labels=concept_labels,
    )

    with _vocab_cache_lock:
        # Remove obsolete hashes for the same document_id
        stale_keys = [k for k in _doc_vocab_cache if k[0] == doc.id and k[1] != content_hash]
        for sk in stale_keys:
            _doc_vocab_cache.pop(sk, None)
        _doc_vocab_cache[cache_key] = profile
        while len(_doc_vocab_cache) > MAX_DOC_VOCAB_CACHE_ENTRIES:
            _doc_vocab_cache.popitem(last=False)

    return profile, False


def get_scoped_terminology(
    db: Session,
    user_id: int,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
) -> dict[str, Any]:
    """
    Build a strictly user-isolated and document-scoped terminology context
    covering single-document, multi-document, all-user-documents, or empty scope.
    Unselected documents and other tenants' documents are strictly excluded.
    """
    if document_id is not None and document_ids is not None:
        if set(document_ids) != {document_id}:
            raise HTTPException(
                status_code=400,
                detail="Conflicting document scopes: document_id and document_ids specify different documents.",
            )

    effective_ids: list[int] | None = None
    if document_ids is not None:
        effective_ids = list(dict.fromkeys(document_ids))
    elif document_id is not None:
        effective_ids = [document_id]

    if effective_ids is not None:
        if len(effective_ids) == 0:
            return {
                "has_evidence": False,
                "document_count": 0,
                "documents": [],
                "cache_hit": True,
                "acronyms": {},
                "technical_terms": {},
                "phrases": {},
                "bigrams": Counter(),
                "cooccurrence_map": {},
                "prefixed_numbers": {},
                "lowercase_word_freq": Counter(),
            }
        docs = (
            db.query(Document)
            .filter(Document.user_id == user_id, Document.id.in_(effective_ids))
            .all()
        )
        owned_map = {d.id: d for d in docs}
        if len(owned_map) != len(effective_ids):
            raise HTTPException(
                status_code=404,
                detail="One or more selected documents were not found.",
            )
        scoped_docs = [owned_map[did] for did in effective_ids]
    else:
        scoped_docs = (
            db.query(Document)
            .filter(Document.user_id == user_id)
            .order_by(Document.id.asc())
            .all()
        )

    if not scoped_docs:
        return {
            "has_evidence": False,
            "document_count": 0,
            "documents": [],
            "cache_hit": True,
            "acronyms": {},
            "technical_terms": {},
            "phrases": {},
            "bigrams": Counter(),
            "cooccurrence_map": {},
            "prefixed_numbers": {},
            "lowercase_word_freq": Counter(),
        }

    profiles_with_hits = [get_document_vocabulary_profile(doc, db) for doc in scoped_docs]
    all_cache_hit = all(hit for _, hit in profiles_with_hits)
    bundle_key = (
        user_id,
        tuple((p.document_id, p.content_hash) for p, _ in profiles_with_hits),
    )

    with _vocab_cache_lock:
        cached_bundle = _scoped_bundle_cache.get(bundle_key)
        if cached_bundle is not None:
            _scoped_bundle_cache.move_to_end(bundle_key)
            # Return shallow wrapper carrying live cache_hit flag
            return {**cached_bundle, "cache_hit": all_cache_hit}

    merged_acronyms: dict[str, dict[str, Any]] = {}
    merged_terms: dict[str, dict[str, Any]] = {}
    merged_phrases: dict[str, dict[str, Any]] = {}
    merged_bigrams: Counter = Counter()
    merged_cooccurrence: dict[str, set[str]] = {}
    merged_numbers: dict[str, list[dict[str, Any]]] = {}
    merged_lower_freq: Counter = Counter()
    doc_summaries: list[dict[str, Any]] = []

    for profile, _hit in profiles_with_hits:
        doc_summaries.append({
            "id": profile.document_id,
            "title": profile.document_title,
            "filename": profile.filename,
            "is_handwritten": profile.is_handwritten,
            "content_hash": profile.content_hash,
        })

        for k, meta in profile.acronyms.items():
            entry = merged_acronyms.get(k)
            if not entry:
                merged_acronyms[k] = {
                    **meta,
                    "doc_titles": {profile.document_title},
                    "doc_ids": {profile.document_id},
                }
            else:
                entry["freq"] += meta["freq"]
                entry["in_heading"] = entry["in_heading"] or meta["in_heading"]
                entry["in_definition"] = entry["in_definition"] or meta["in_definition"]
                entry["in_concept"] = entry["in_concept"] or meta["in_concept"]
                entry["domain_match"] = entry["domain_match"] or meta["domain_match"]
                if not entry.get("expansion") and meta.get("expansion"):
                    entry["expansion"] = meta["expansion"]
                entry["doc_titles"].add(profile.document_title)
                entry["doc_ids"].add(profile.document_id)

        for k, meta in profile.technical_terms.items():
            entry = merged_terms.get(k)
            if not entry:
                merged_terms[k] = {
                    **meta,
                    "doc_titles": {profile.document_title},
                    "doc_ids": {profile.document_id},
                }
            else:
                entry["freq"] += meta["freq"]
                entry["in_heading"] = entry["in_heading"] or meta["in_heading"]
                entry["in_concept"] = entry["in_concept"] or meta["in_concept"]
                entry["in_title"] = entry["in_title"] or meta["in_title"]
                entry["doc_titles"].add(profile.document_title)
                entry["doc_ids"].add(profile.document_id)

        for k, meta in profile.phrases.items():
            entry = merged_phrases.get(k)
            if not entry:
                merged_phrases[k] = {**meta, "doc_titles": {profile.document_title}}
            else:
                entry["freq"] += meta["freq"]
                entry["in_heading"] = entry["in_heading"] or meta["in_heading"]
                entry["in_concept"] = entry["in_concept"] or meta["in_concept"]
                entry["doc_titles"].add(profile.document_title)

        merged_bigrams.update(profile.bigrams)
        merged_lower_freq.update(profile.lowercase_word_freq)

        for term_k, co_words in profile.cooccurrence_map.items():
            merged_cooccurrence.setdefault(term_k, set()).update(co_words)

        for pref, items in profile.prefixed_numbers.items():
            target_lst = merged_numbers.setdefault(pref, [])
            for item in items:
                ex = next((x for x in target_lst if x["number"] == item["number"]), None)
                if ex:
                    ex["freq"] += item["freq"]
                    ex["doc_titles"].add(profile.document_title)
                else:
                    target_lst.append({
                        **item,
                        "doc_titles": {profile.document_title},
                    })

    has_any_vocab = bool(merged_acronyms or merged_terms or merged_phrases)
    bundle = {
        "has_evidence": has_any_vocab,
        "document_count": len(scoped_docs),
        "documents": doc_summaries,
        "acronyms": merged_acronyms,
        "technical_terms": merged_terms,
        "phrases": merged_phrases,
        "bigrams": merged_bigrams,
        "cooccurrence_map": merged_cooccurrence,
        "prefixed_numbers": merged_numbers,
        "lowercase_word_freq": merged_lower_freq,
    }
    with _vocab_cache_lock:
        _scoped_bundle_cache[bundle_key] = bundle
        while len(_scoped_bundle_cache) > MAX_SCOPED_BUNDLE_CACHE_ENTRIES:
            _scoped_bundle_cache.popitem(last=False)

    return {**bundle, "cache_hit": all_cache_hit}


_PROMPT_BIGRAM_STOPWORDS = {
    "is", "are", "was", "were", "and", "or", "by", "of",
    "the", "a", "an", "to", "in", "on", "for", "with", "at", "as", "from",
}
_PROMPT_PHRASE_LEADING_STOPWORDS = {"the", "a", "an", "for", "of", "in", "on", "to"}


def build_whisper_initial_prompt(
    db: Session,
    user_id: int,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    max_terms: int = 14,
    max_chars: int = 220,
) -> str | None:
    """
    Build a concise, bounded Whisper `initial_prompt` from the authenticated user's
    scoped document vocabulary to anchor short technical acronyms and compound terms
    without biasing unrelated normal English speech or leaking across tenants.
    """
    bundle = get_scoped_terminology(
        db=db,
        user_id=user_id,
        document_id=document_id,
        document_ids=document_ids,
    )
    if not bundle.get("has_evidence"):
        return None

    ranked: list[tuple[float, str]] = []
    seen_lower: set[str] = set()
    acronyms = bundle.get("acronyms") or {}

    for key, meta in acronyms.items():
        canon = str(meta.get("canonical") or key).strip()
        if not canon or canon.lower() in ORDINARY_ENGLISH_WORDS:
            continue
        freq = int(meta.get("freq", 1))
        if freq < 2 and not meta.get("in_heading") and not meta.get("domain_match"):
            continue
        score = (
            freq * 3.0
            + (4.0 if meta.get("in_heading") else 0.0)
            + (3.0 if meta.get("domain_match") else 0.0)
            + (2.0 if meta.get("in_definition") else 0.0)
        )
        if canon.lower() not in seen_lower:
            seen_lower.add(canon.lower())
            ranked.append((score, canon))

    for pref, items in (bundle.get("prefixed_numbers") or {}).items():
        for item in items:
            label = f"{pref.upper()} {item['number']}".strip()
            if label.lower() not in seen_lower:
                seen_lower.add(label.lower())
                ranked.append((5.0 + float(item.get("freq", 1)) * 2.0, label))

    for bg, cnt in (bundle.get("bigrams") or {}).items():
        parts = list(bg) if isinstance(bg, tuple) else str(bg).split()
        if len(parts) != 2 or int(cnt) < 2:
            continue
        head_key = parts[0].upper()
        tail = parts[1].lower()
        if (
            head_key not in acronyms
            or parts[0].lower() in ORDINARY_ENGLISH_WORDS
            or not re.fullmatch(r"[a-z]{3,}", tail)
            or tail in _PROMPT_BIGRAM_STOPWORDS
        ):
            continue
        head_canon = str(acronyms[head_key].get("canonical") or head_key).strip()
        phrase = f"{head_canon} {parts[1]}"
        if phrase.lower() not in seen_lower:
            seen_lower.add(phrase.lower())
            ranked.append((6.0 + float(cnt) * 3.0, phrase))

    for key, meta in (bundle.get("phrases") or {}).items():
        canon = str(meta.get("canonical") or key).strip()
        first = canon.split(" ", 1)[0].lower() if canon else ""
        if not canon or first in _PROMPT_PHRASE_LEADING_STOPWORDS or len(canon) > 32:
            continue
        freq = int(meta.get("freq", 1))
        if freq < 2 and not meta.get("in_heading") and not meta.get("in_concept"):
            continue
        words = canon.split()
        lead_key = words[0].upper()
        if lead_key in acronyms and words[0].lower() not in ORDINARY_ENGLISH_WORDS:
            words[0] = str(acronyms[lead_key].get("canonical") or lead_key).strip()
            canon = " ".join(words)
        if canon.lower() not in seen_lower:
            seen_lower.add(canon.lower())
            score = (
                freq * 2.0
                + (3.0 if meta.get("in_heading") else 0.0)
                + (2.0 if meta.get("in_concept") else 0.0)
            )
            ranked.append((score, canon))

    for key, meta in (bundle.get("technical_terms") or {}).items():
        canon = str(meta.get("canonical") or key).strip()
        if not canon or len(canon) < 3 or meta.get("in_title") or canon.lower() in seen_lower:
            continue
        freq = int(meta.get("freq", 1))
        if freq < 2 and not meta.get("in_heading"):
            continue
        seen_lower.add(canon.lower())
        ranked.append((float(freq) + (2.0 if meta.get("in_heading") else 0.0), canon))

    if not ranked:
        return None

    ranked.sort(key=lambda item: (-item[0], item[1]))
    chosen: list[str] = []
    prefix = "Document terminology: "
    current_len = len(prefix) + 1  # account for trailing period
    for _, term in ranked[:max_terms]:
        addition = (2 if chosen else 0) + len(term)
        if current_len + addition > max_chars:
            break
        chosen.append(term)
        current_len += addition

    if not chosen:
        return None
    return f"{prefix}{', '.join(chosen)}."

