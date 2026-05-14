from __future__ import annotations

from functools import lru_cache

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # pragma: no cover - depends on runtime model availability
        raise RuntimeError(
            f"SentenceTransformer dependency for '{MODEL_NAME}' could not be imported."
        ) from exc

    return SentenceTransformer(MODEL_NAME)


def embed(text: str) -> list[float]:
    model = _get_model()
    vector = model.encode(text[:8000], normalize_embeddings=True)
    return vector.tolist()
