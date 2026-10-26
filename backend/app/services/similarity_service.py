import math


def cosine_similarity(
    embedding1: list[float],
    embedding2: list[float],
    magnitude1: float | None = None
) -> float:
    """
    Calculate cosine similarity between two embeddings.
    Accepts an optional pre-computed magnitude1 for embedding1 to eliminate
    redundant calculations across multi-document searches.
    """

    if len(embedding1) != len(embedding2):
        raise ValueError(
            "Embeddings must have the same dimensions."
        )

    dot_product = sum(
        a * b
        for a, b in zip(embedding1, embedding2)
    )

    if magnitude1 is None:
        magnitude1 = math.sqrt(
            sum(a * a for a in embedding1)
        )

    magnitude2 = math.sqrt(
        sum(b * b for b in embedding2)
    )

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)