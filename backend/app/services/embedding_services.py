from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


def generate_embedding(text: str) -> list[float]:
    """
    Generate a semantic embedding for the given text.
    """

    embedding = model.encode(
        text,
        convert_to_numpy=True
    )

    return embedding.tolist()