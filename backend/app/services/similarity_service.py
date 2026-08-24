import math


def cosine_similarity(
    embedding1: list[float],
    embedding2: list[float]
) -> float:
    """
    Calculate cosine similarity between two embeddings.
    """

    if len(embedding1) != len(embedding2):
        raise ValueError(
            "Embeddings must have the same dimensions."
        )

    dot_product = sum(
        a * b
        for a, b in zip(embedding1, embedding2)
    )

    magnitude1 = math.sqrt(
        sum(a * a for a in embedding1)
    )

    magnitude2 = math.sqrt(
        sum(b * b for b in embedding2)
    )

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)