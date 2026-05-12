from __future__ import annotations

import math
import re
from functools import lru_cache

from app.services.resume.embedder import embed

SECTION_PATTERNS = {
    "experience": re.compile(r"\b(experience|work history|employment history|professional experience)\b", re.I),
    "education": re.compile(r"\b(education|academic background|qualifications)\b", re.I),
    "skills": re.compile(r"\b(skills|technical skills|core competencies|expertise)\b", re.I),
    "contact": re.compile(r"\b(contact|contact information|email)\b", re.I),
}
REFERENCE_TEMPLATE = "professional experience skills education projects contact information"


def structural_score(text: str) -> float:
    sections_found = sum(1 for pattern in SECTION_PATTERNS.values() if pattern.search(text))
    return sections_found / 4


@lru_cache(maxsize=1)
def _reference_embedding() -> tuple[float, ...]:
    return tuple(embed(REFERENCE_TEMPLATE))


def semantic_score(text: str, embedding: list[float]) -> float:
    del text
    reference_embedding = _reference_embedding()
    if not embedding or len(embedding) != len(reference_embedding):
        return 0.0

    dot_product = sum(left * right for left, right in zip(embedding, reference_embedding, strict=True))
    embedding_norm = math.sqrt(sum(value * value for value in embedding))
    reference_norm = math.sqrt(sum(value * value for value in reference_embedding))
    if embedding_norm == 0.0 or reference_norm == 0.0:
        return 0.0

    similarity = dot_product / (embedding_norm * reference_norm)
    return max(0.0, min(1.0, similarity))
