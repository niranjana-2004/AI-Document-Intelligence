from app.services.embedding_services import generate_embedding
from app.services.similarity_service import cosine_similarity
from app.models.document_chunk import DocumentChunk
import re


SIMILARITY_THRESHOLD = 0.20
FINAL_SCORE_THRESHOLD = 0.20

SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30


# Common abbreviations and their full forms
QUERY_EXPANSIONS = {
    "bca": "Bachelor of Computer Applications",
    "mca": "Master of Computer Applications",
}


def expand_query(query: str) -> str:
    """
    Expand common abbreviations in the user's query
    so that semantic search can match their full forms.
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


def calculate_keyword_score(query: str, content: str) -> float:
    """
    Calculate keyword/concept overlap between the query
    and document chunk.

    Known abbreviations such as BCA/MCA are treated as
    equivalent to their full forms.
    """

    query_words = set(
        re.findall(r"\b[a-zA-Z0-9]+\b", query.lower())
    )

    content_words = set(
        re.findall(r"\b[a-zA-Z0-9]+\b", content.lower())
    )

    if not query_words:
        return 0.0

    matched_words = query_words.intersection(content_words)

    # Check abbreviation/full-form equivalence
    for abbreviation, full_form in QUERY_EXPANSIONS.items():

        if abbreviation in query_words:

            full_form_words = set(
                re.findall(
                    r"\b[a-zA-Z0-9]+\b",
                    full_form.lower()
                )
            )

            # If the full form exists in the content,
            # count the abbreviation as a matched concept.
            if full_form_words.issubset(content_words):
                matched_words.add(abbreviation)

    return len(matched_words) / len(query_words)


def semantic_search(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 5
):
    """
    Perform hybrid semantic + keyword search.
    """

    # Expand abbreviations before generating the embedding.
    expanded_query = expand_query(query)

    query_embedding = generate_embedding(expanded_query)

    query_db = db.query(DocumentChunk)

    if document_id is not None:
        query_db = query_db.filter(
            DocumentChunk.document_id == document_id
        )

    chunks = query_db.all()

    results = []

    for chunk in chunks:

        if not chunk.embedding:
            continue

        similarity = cosine_similarity(
            query_embedding,
            chunk.embedding
        )

        # Ignore chunks that are not semantically relevant
        if similarity < SIMILARITY_THRESHOLD:
            continue

        keyword_score = calculate_keyword_score(
            query,
            chunk.content
        )

        final_score = (
            SEMANTIC_WEIGHT * similarity
            + KEYWORD_WEIGHT * keyword_score
        )

        if final_score >= FINAL_SCORE_THRESHOLD:

            results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "similarity": similarity,
                "keyword_score": keyword_score,
                "final_score": final_score
            })

    results.sort(
        key=lambda x: x["final_score"],
        reverse=True
    )

    return results[:top_k]