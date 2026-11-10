import math
import re
from pathlib import Path
from typing import cast
from app.models.document import Document
from app.services.embedding_services import generate_embedding
from app.services.similarity_service import cosine_similarity
from app.services.text_processing_service import extract_relevant_excerpt
from app.models.document_chunk import DocumentChunk


def clean_document_title(filename: str | None) -> str:
    """Clean filename into a clean, human-readable document title."""
    if not filename:
        return "Document"
    stem = Path(filename).stem
    cleaned = re.sub(r"[\+_\-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "Document"


def balance_cross_document_diversity(
    results: list[dict],
    top_k: int = 6,
    is_multi_document: bool = False
) -> list[dict]:
    """
    Balance evidence representation across multiple selected documents.
    1. Removes near-duplicate chunks within the same document.
    2. Groups candidates by document_id in descending score order.
    3. Stratifies selection across represented documents so no single document
       starves other qualifying relevant documents, while preserving overall score ranking.
    4. If only one document has qualifying evidence, it naturally retains all slots.
    """
    if not results:
        return []

    # 1. Deduplicate near-identical chunks within the same document
    deduped_results = []
    seen_texts: dict[int, list[str]] = {}

    for r in results:
        doc_id = r["document_id"]
        text_clean = re.sub(r"\s+", " ", (r.get("content") or "").strip().lower())
        if not text_clean:
            continue

        if doc_id not in seen_texts:
            seen_texts[doc_id] = []

        is_dup = False
        words_r = set(text_clean.split())
        for existing in seen_texts[doc_id]:
            words_existing = set(existing.split())
            if not words_r or not words_existing:
                continue
            jaccard = len(words_r & words_existing) / len(words_r | words_existing)
            if jaccard >= 0.82 or text_clean in existing or existing in text_clean:
                is_dup = True
                break

        if not is_dup:
            seen_texts[doc_id].append(text_clean)
            deduped_results.append(r)

    if not is_multi_document or len(seen_texts) <= 1:
        return deduped_results[:top_k]

    # 2. Group chunks by document
    docs_chunks: dict[int, list[dict]] = {}
    for r in deduped_results:
        docs_chunks.setdefault(r["document_id"], []).append(r)

    # Sort documents by their top-scoring chunk descending
    sorted_doc_ids = sorted(
        docs_chunks.keys(),
        key=lambda d: cast(float, docs_chunks[d][0]["final_score"]),
        reverse=True
    )

    # 3. Stratified round-robin selection with soft-capping
    num_qualifying_docs = len(sorted_doc_ids)
    max_per_doc = max(2, math.ceil(top_k / num_qualifying_docs) + 1)

    selected: list[dict] = []
    round_idx = 0

    while len(selected) < top_k:
        added_in_this_pass = False
        for d in sorted_doc_ids:
            chunks = docs_chunks[d]
            doc_selected_count = sum(1 for s in selected if s["document_id"] == d)
            if round_idx < len(chunks):
                if doc_selected_count < max_per_doc or (len(selected) + (len(sorted_doc_ids) - sorted_doc_ids.index(d)) > top_k):
                    selected.append(chunks[round_idx])
                    added_in_this_pass = True
                    if len(selected) >= top_k:
                        break
        round_idx += 1
        if not added_in_this_pass:
            # If all docs reached their soft caps or ran out of round_idx, fill remaining slots by best score
            remaining = [r for r in deduped_results if r not in selected]
            remaining.sort(key=lambda x: cast(float, x["final_score"]), reverse=True)
            for r in remaining:
                if len(selected) >= top_k:
                    break
                selected.append(r)
            break

    # Re-sort selected by final_score descending so highest score is always [Source 1]
    selected.sort(key=lambda x: cast(float, x["final_score"]), reverse=True)
    return selected[:top_k]


# --------------------------------------------------
# SEARCH THRESHOLDS / WEIGHTS
# --------------------------------------------------

SIMILARITY_THRESHOLD = 0.25
FINAL_SCORE_THRESHOLD = 0.25

SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30


# --------------------------------------------------
# COMMON STOP WORDS (FOR KEYWORD FILTERING)
# --------------------------------------------------

ENGLISH_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd",
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}


# --------------------------------------------------
# QUERY EXPANSIONS
# --------------------------------------------------

QUERY_EXPANSIONS = {
    "bca": "Bachelor of Computer Applications",
    "mca": "Master of Computer Applications",
}


# --------------------------------------------------
# SPECIFIC QUERY INTENTS
# --------------------------------------------------

QUERY_INTENTS = {
    "programming_languages": [
        "programming language",
        "programming languages",
        "coding language",
        "coding languages",
    ],

    "web_frameworks": [
        "web technology",
        "web technologies",
        "framework",
        "frameworks",
        "web framework",
        "web frameworks",
    ],

    "databases": [
        "database",
        "databases",
        "database management",
    ],

    "tools": [
        "tools",
        "tools and platforms",
        "tools platforms",
    ],

    "ides": [
        "ide",
        "ides",
        "integrated development environment",
    ],

    "operating_systems": [
        "operating system",
        "operating systems",
    ],

    "technical_skills": [
        "technical skill",
        "technical skills",
    ],

    "certifications": [
        "certification",
        "certifications",
        "certificate",
        "certificates",
    ],

    "objective": [
        "objective",
        "objectives",
        "project objective",
        "project objectives",
        "aim of the project",
        "goal of the project",
        "project goal",
        "project goals",
        "career objective",
    ],

    "projects": [
        "projects done",
        "projects have i done",
        "projects has he done",
        "projects has she done",
        "projects did i do",
        "projects did he do",
        "projects did she do",
        "projects worked on",
        "projects completed",
        "list of projects",
        "list projects",
        "list all projects",
        "what projects",
        "which projects",
        "my projects",
        "academic projects",
        "personal projects",
        "projects listed",
        "projects undertaken",
    ],

    "internship": [
        "internship",
        "internships",
        "intern",
    ],

    "workshops": [
        "workshop",
        "workshops",
        "bootcamp",
    ],

    "awards": [
        "award",
        "awards",
        "achievement",
        "achievements",
    ],

    "education": [
        "education",
        "educational",
        "qualification",
        "qualifications",
        "degree",
        "cgpa",
        "percentage",
        "bca",
        "mca",
        "bachelor",
        "master",
    ],

    "languages": [
    "spoken language",
    "spoken languages",
    "languages known",
    ],

    "ambiguous_languages": [
    "what languages",
    "which languages",
    ]
}


# --------------------------------------------------
# DOCUMENT SECTION MARKERS
# --------------------------------------------------

SECTION_MARKERS = {

    "objective": [
        "career objective",
        "main objective",
        "project objective",
        "project objectives",
        "objective of the project",
        "objective of this project",
        "specific objectives",
        "aim of the project",
        "objective:",
        "objectives:",
        "objective\n",
        "objectives\n",
    ],

    "education": [
        "educational qualifications",
        "higher secondary education",
        "secondary school education",
    ],

    "projects": [
        "projects done",
    ],

    "internship": [
        "internships done",
    ],

    "workshops": [
        "workshops done",
    ],

    "technical_skills": [
        "technical skills",
    ],

    "awards": [
        "awards and achievements",
    ],

    "languages": [
        "languages known",
    ],

    "certifications": [
        "certifications done",
    ],
}


# --------------------------------------------------
# SPECIFIC SUBSECTION MARKERS
# --------------------------------------------------

SUBSECTION_MARKERS = {

    "programming_languages": [
        "programming languages:",
    ],

    "web_frameworks": [
        "web & frameworks:",
        "web and frameworks:",
    ],

    "databases": [
        "database management:",
        "databases:",
    ],

    "tools": [
        "tools & platforms:",
        "tools and platforms:",
    ],

    "ides": [
        "ides:",
    ],

    "operating_systems": [
        "operating systems:",
    ],
}


# --------------------------------------------------
# QUERY EXPANSION
# --------------------------------------------------

def expand_query(query: str) -> str:
    """
    Expand common abbreviations before generating
    the semantic embedding.
    """

    expanded_query = query

    for abbreviation, full_form in QUERY_EXPANSIONS.items():

        pattern = rf"\b{re.escape(abbreviation)}\b"

        expanded_query = re.sub(
            pattern,
            f"{abbreviation} {full_form}",
            expanded_query,
            flags=re.IGNORECASE
        )

    return expanded_query


# --------------------------------------------------
# QUERY INTENT DETECTION
# --------------------------------------------------

def detect_query_intent(query: str) -> str | None:
    """
    Detect the most specific information requested
    by the user.
    """

    query_lower = query.lower().strip()

    # Most specific categories first
    priority = [
        "programming_languages",
        "web_frameworks",
        "databases",
        "operating_systems",
        "ides",
        "tools",
        "certifications",
        "objective",
        "projects",
        "workshops",
        "awards",
        "education",
        "internship",
        "ambiguous_languages",
        "languages",
        "technical_skills",
    ]

    for intent in priority:

        for keyword in QUERY_INTENTS[intent]:

            if re.search(
                rf"\b{re.escape(keyword)}\b",
                query_lower
            ):
                return intent

    return None

def is_ambiguous_language_query(query: str) -> bool:
    """
    Detect questions that ask generally about "languages"
    without specifying programming or spoken languages.
    """

    query_lower = query.lower().strip()

    # Explicit programming-language queries are not ambiguous
    programming_phrases = [
        "programming language",
        "programming languages",
        "coding language",
        "coding languages",
    ]

    # Explicit spoken-language queries are not ambiguous
    spoken_phrases = [
        "spoken language",
        "spoken languages",
    ]

    if any(
        phrase in query_lower
        for phrase in programming_phrases + spoken_phrases
    ):
        return False

    # General language question
    return bool(
        re.search(r"\bwhat languages\b", query_lower)
        or re.search(r"\bwhich languages\b", query_lower)
        or re.search(r"\blanguages does\b", query_lower)
    )


def is_overview_or_summary_query(query: str) -> bool:
    """
    Detect document-level overview, summary, comparison, or description queries
    (e.g., 'What is this document about?', 'Compare the main ideas in these two documents').
    """
    q = query.lower().strip()
    patterns = [
        r"what (is|are) (this|the|these|it) (document|documents|file|notes)?\s*about",
        r"what does (this|the) document (discuss|say|cover|talk about)",
        r"(summarize|summary of|overview of)\s*(the\s+)?(key\s+|main\s+)?(topics|concepts|notes|ideas|content)?",
        r"(summarize|summary of|overview of) (this|the|these) (document|documents|file)?",
        r"tell me about (this|the|these) document",
        r"what (is|are) in (this|the|these) document",
        r"compare (the\s+)?(main\s+|key\s+)?(ideas|concepts|topics|content|sections)?\s*(in|across|between|of)?\s*(these|the|all)?\s*(two|three|\d+)?\s*documents?",
        r"compare (these|the) (documents|files|notes)",
        r"what (is|are) the differences?\s+between (these|the) documents?",
    ]
    return any(re.search(p, q) for p in patterns)

# --------------------------------------------------
# BACKWARD COMPATIBILITY
# --------------------------------------------------

def detect_query_category(query: str) -> str | None:
    """
    Return the broader document category.

    This keeps compatibility with existing code.
    """

    intent = detect_query_intent(query)

    if intent in {
        "programming_languages",
        "web_frameworks",
        "databases",
        "tools",
        "ides",
        "operating_systems",
        "technical_skills",
    }:
        return "technical_skills"

    return intent


# --------------------------------------------------
# QUERY CONTEXT
# --------------------------------------------------

def detect_query_context(query: str) -> str | None:
    """
    Detect contextual constraints in the user's question.
    """

    query_lower = query.lower()

    internship_phrases = [
        "during their internship",
        "during the internship",
        "in their internship",
        "in the internship",
        "while doing their internship",
        "while on their internship",
        "as part of their internship",
    ]

    for phrase in internship_phrases:

        if phrase in query_lower:
            return "internship"

    return None


# --------------------------------------------------
# KEYWORD SCORE
# --------------------------------------------------

def calculate_keyword_score(
    query: str,
    content: str
) -> float:
    """
    Calculate keyword overlap between query and content,
    excluding common English stop words to prevent false positive matches.
    """

    query_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]+\b",
            query.lower()
        )
    )

    content_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]+\b",
            content.lower()
        )
    )

    meaningful_words = {
        w for w in query_words
        if w not in ENGLISH_STOP_WORDS
    }

    if not meaningful_words:
        return 0.0

    def _stem_variants(word: str) -> set[str]:
        variants = {word}
        if len(word) > 4:
            if word.endswith("ies"):
                variants.add(word[:-3] + "y")
            elif word.endswith("es"):
                variants.add(word[:-2])
                variants.add(word[:-1])
            elif word.endswith("s"):
                variants.add(word[:-1])
        return variants

    content_expanded = set(content_words)
    for cw in content_words:
        content_expanded.update(_stem_variants(cw))

    matched_words = {
        w for w in meaningful_words
        if _stem_variants(w).intersection(content_expanded)
    }

    # Abbreviation/full-form matching
    for abbreviation, full_form in QUERY_EXPANSIONS.items():

        if abbreviation in meaningful_words:

            full_form_words = set(
                re.findall(
                    r"\b[a-zA-Z0-9]+\b",
                    full_form.lower()
                )
            )

            if full_form_words.issubset(content_words):

                matched_words.add(
                    abbreviation
                )

    return len(matched_words) / len(meaningful_words)


# --------------------------------------------------
# CATEGORY BOOST
# --------------------------------------------------

def calculate_category_boost(
    category: str | None,
    content: str
) -> float:
    """
    Boost chunks belonging to the requested
    broad document category.
    """

    if category is None:
        return 0.0

    content_lower = content.lower()

    markers = SECTION_MARKERS.get(
        category,
        []
    )

    matches = 0

    for marker in markers:

        if marker in content_lower:
            matches += 1

    if matches == 0:
        return 0.0

    if matches >= 2:
        return 0.50

    return 0.40


# --------------------------------------------------
# SUBSECTION BOOST
# --------------------------------------------------

def calculate_subsection_boost(
    intent: str | None,
    content: str
) -> float:
    """
    Strongly boost chunks containing the exact
    subsection requested by the user.
    """

    if intent is None:
        return 0.0

    markers = SUBSECTION_MARKERS.get(
        intent,
        []
    )

    if not markers:
        return 0.0

    content_lower = content.lower()

    for marker in markers:

        if marker in content_lower:
            return 0.80

    return 0.0


# --------------------------------------------------
# SEARCH
# --------------------------------------------------

def semantic_search(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 5,
    user_id: int | None = None,
    document_ids: list[int] | None = None
):
    """
    Perform hybrid semantic + keyword +
    category + subsection search.
    """

    expanded_query = expand_query(query)

    query_embedding = generate_embedding(
        expanded_query
    )

    query_magnitude = math.sqrt(
        sum(a * a for a in query_embedding)
    )

    intent = detect_query_intent(query)

    category = detect_query_category(query)

    query_context = detect_query_context(query)

    ambiguous_language_query = is_ambiguous_language_query(query)
    overview_query = is_overview_or_summary_query(query)

    # Ambiguous "languages" queries should search both
    # programming languages and spoken languages.
    if intent == "ambiguous_languages":
        intent = None
        category = None

    query_db = (
        db.query(DocumentChunk, Document.filename, Document.is_handwritten, Document.document_type)
        .join(Document, Document.id == DocumentChunk.document_id)
    )
    if user_id is not None:
        query_db = query_db.filter(Document.user_id == user_id)
    if document_ids is not None:
        query_db = query_db.filter(
            DocumentChunk.document_id.in_(document_ids)
        )
    elif document_id is not None:
        query_db = query_db.filter(
            DocumentChunk.document_id == document_id
        )

    chunk_rows = query_db.all()

    chunks = []
    doc_meta = {}
    for chunk, fname, is_hw, doc_type in chunk_rows:
        chunks.append(chunk)
        if chunk.document_id not in doc_meta:
            doc_meta[chunk.document_id] = {
                "filename": fname,
                "is_handwritten": bool(is_hw),
                "document_type": doc_type or ("HANDWRITTEN" if is_hw else "PDF")
            }

    results = []

    # --------------------------------------------------
    # Ambiguous language query
    # --------------------------------------------------

    if ambiguous_language_query:

        programming_chunks = []
        spoken_language_chunks = []

        for chunk in chunks:

            if not chunk.embedding:
                continue

            content_lower = chunk.content.lower()

            # Programming Languages section
            if "programming languages:" in content_lower:
                programming_chunks.append(chunk)

            # Spoken Languages section
            elif "languages known" in content_lower:
                spoken_language_chunks.append(chunk)

        # Force both language categories into the result set
        special_chunks = (
            programming_chunks +
            spoken_language_chunks
        )

    else:
        special_chunks = []

    # --------------------------------------------------
    # Resolve ambiguous "language" queries
    # --------------------------------------------------

    if ambiguous_language_query:
        query_intent = "languages"
        category = "languages"

    chunks_to_search = special_chunks if ambiguous_language_query else chunks

    # Precompute section and subsection presence in candidate documents
    SECTION_FILTER_INTENTS = {
        "projects": "projects",
        "certifications": "certifications",
        "internship": "internship",
        "workshops": "workshops",
        "awards": "awards",
        "education": "education",
        "languages": "languages",
    }

    has_section_marker_in_docs = False
    if intent in SECTION_FILTER_INTENTS:
        required_category = SECTION_FILTER_INTENTS[intent]
        section_markers = SECTION_MARKERS.get(required_category, [])
        has_section_marker_in_docs = any(
            any(marker in (c.content or "").lower() for marker in section_markers)
            for c in chunks_to_search
        )

    has_subsection_marker_in_docs = False
    if intent in SUBSECTION_MARKERS:
        has_subsection_marker_in_docs = any(
            any(marker in (c.content or "").lower() for marker in SUBSECTION_MARKERS[intent])
            for c in chunks_to_search
        )

    for chunk in chunks_to_search:

        if not chunk.embedding:
            continue

        # --------------------------------------------------
        # Early context filtering
        # --------------------------------------------------

        if query_context == "internship":

            chunk_category = (
                chunk.category or ""
            ).lower()

            if chunk_category != "internship":
                continue

        content_lower = chunk.content.lower()

        # --------------------------------------------------
        # Early document section filtering
        # --------------------------------------------------

        if intent in SECTION_FILTER_INTENTS and has_section_marker_in_docs:

            required_category = SECTION_FILTER_INTENTS[intent]

            section_markers = SECTION_MARKERS.get(
                required_category,
                []
            )

            section_present = any(
                marker in content_lower 
                for marker in section_markers
            )

            if not section_present:
                continue

        # --------------------------------------------------
        # Early subsection filtering
        # --------------------------------------------------

        if intent in SUBSECTION_MARKERS and has_subsection_marker_in_docs:

            subsection_present = False

            for marker in SUBSECTION_MARKERS[intent]:

                if marker in content_lower:
                    subsection_present = True
                    break

            # For specific subsection queries, only return
            # chunks that actually contain that subsection.
            if not subsection_present:
                continue

        # --------------------------------------------------
        # Ambiguous language query boost
        # --------------------------------------------------

        language_category_boost = 0.0

        if ambiguous_language_query:

            if "languages known" in content_lower:
                language_category_boost = 0.80

            elif "programming languages:" in content_lower:
                language_category_boost = 0.40

        similarity = cosine_similarity(
            query_embedding,
            chunk.embedding,
            magnitude1=query_magnitude
        )

        keyword_score = calculate_keyword_score(
            query,
            chunk.content
        )

        category_boost = calculate_category_boost(
            category,
            chunk.content
        )

        subsection_boost = calculate_subsection_boost(
            intent,
            chunk.content
        )

        overview_boost = 0.0
        if overview_query:
            # Introductory and early chunks provide primary document overview
            chunk_idx = getattr(chunk, "chunk_index", 0) or 0
            overview_boost = 0.40 if chunk_idx <= 1 else 0.20

        # --------------------------------------------------
        # General relevance filtering
        # --------------------------------------------------

        if (
            not overview_query
            and similarity < SIMILARITY_THRESHOLD
            and keyword_score == 0
            and category_boost == 0
            and subsection_boost == 0
        ):
            continue

        # --------------------------------------------------
        # Final score
        # --------------------------------------------------

        final_score = (
            SEMANTIC_WEIGHT * similarity
            + KEYWORD_WEIGHT * keyword_score
            + category_boost
            + subsection_boost
            + language_category_boost
            + overview_boost
        )

        if final_score >= FINAL_SCORE_THRESHOLD:
            meta = doc_meta.get(chunk.document_id, {})
            fname = meta.get("filename") or "Document"
            is_hw = meta.get("is_handwritten", False)
            doc_type = meta.get("document_type", "PDF")
            doc_title = clean_document_title(fname)
            page_num = getattr(chunk, "page_number", None)

            results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_name": fname,
                "document_title": doc_title,
                "filename": fname,
                "document_type": doc_type,
                "source_type": "handwritten" if is_hw else "printed",
                "page_number": page_num,
                "page": page_num,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "source_text": chunk.content,
                "excerpt": extract_relevant_excerpt(chunk.content, query, max_chars=240),
                "similarity": round(similarity, 4),
                "retrieval_score": round(final_score, 4),
                "keyword_score": round(keyword_score, 4),
                "category": category,
                "query_intent": intent,
                "category_boost": category_boost,
                "subsection_boost": subsection_boost,
                "final_score": round(final_score, 4)
            })

    results.sort(
        key=lambda x: cast(float, x["final_score"]),
        reverse=True
    )

    is_multi = (document_ids is not None and len(document_ids) > 1)

    # Relative drop-off filter:
    # Retain chunks within 60% of the top score (50% in multi-document mode so
    # relevant documents covering a second sub-topic are not starved prior to
    # cross-document diversity balancing), filtering out unrelated noise.
    if results:
        top_score = cast(float, results[0]["final_score"])
        dropoff_factor = 0.50 if is_multi else 0.60
        results = [
            r for r in results
            if cast(float, r["final_score"]) >= top_score * dropoff_factor
        ]

    return balance_cross_document_diversity(results, top_k=top_k, is_multi_document=is_multi)