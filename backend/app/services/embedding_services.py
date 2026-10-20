import threading
from typing import Any


MODEL_NAME = "all-MiniLM-L6-v2"

_model: Any = None
_model_lock = threading.Lock()


def get_embedding_model() -> Any:
    """
    Lazily initialize and return the thread-safe singleton SentenceTransformer model.
    The model is loaded on the first embedding request rather than on application startup.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(MODEL_NAME)
    return _model


def generate_embedding(text: str) -> list[float]:
    """
    Generate a semantic embedding for the given text.
    Preserves exact dimensions, model name, and float vector output.
    """
    model_instance = get_embedding_model()

    embedding = model_instance.encode(
        text,
        convert_to_numpy=True
    )

    return embedding.tolist()


def __getattr__(name: str) -> Any:
    """
    Backward-compatibility hook in case legacy code or tests access `model` directly.
    """
    if name == "model":
        return get_embedding_model()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["MODEL_NAME", "get_embedding_model", "generate_embedding", "model"]
