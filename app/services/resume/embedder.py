from __future__ import annotations

MODEL_NAME = "all-MiniLM-L6-v2"

try:
    from sentence_transformers import SentenceTransformer

    MODEL = SentenceTransformer(MODEL_NAME)
    MODEL_LOAD_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - depends on runtime model availability
    MODEL = None
    MODEL_LOAD_ERROR = exc


def embed(text: str) -> list[float]:
    if MODEL is None:
        raise RuntimeError(f"SentenceTransformer model '{MODEL_NAME}' could not be loaded.") from MODEL_LOAD_ERROR

    vector = MODEL.encode(text[:8000], normalize_embeddings=True)
    return vector.tolist()
