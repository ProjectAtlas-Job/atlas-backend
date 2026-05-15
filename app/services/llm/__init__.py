from __future__ import annotations

import re
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_SKILL_PATTERNS = {
    "python": r"\bpython\b",
    "django": r"\bdjango\b",
    "fastapi": r"\bfastapi\b",
    "flask": r"\bflask\b",
    "java": r"\bjava\b",
    "spring": r"\bspring(?: boot)?\b",
    "javascript": r"\bjavascript\b",
    "typescript": r"\btypescript\b",
    "nodejs": r"\bnode(?:\.?js)?\b",
    "react": r"\breact(?:\.js)?\b",
    "nextjs": r"\bnext(?:\.?js)?\b",
    "angular": r"\bangular\b",
    "vue": r"\bvue(?:\.js)?\b",
    "html": r"\bhtml\b",
    "css": r"\bcss\b",
    "sql": r"\bsql\b",
    "postgres": r"\bpostgres(?:ql)?\b",
    "mysql": r"\bmysql\b",
    "mongodb": r"\bmongodb\b",
    "redis": r"\bredis\b",
    "aws": r"\baws\b|\bamazon web services\b",
    "gcp": r"\bgcp\b|\bgoogle cloud\b",
    "azure": r"\bazure\b",
    "docker": r"\bdocker\b",
    "kubernetes": r"\bkubernetes\b|\bk8s\b",
    "git": r"\bgit\b",
    "linux": r"\blinux\b",
    "graphql": r"\bgraphql\b",
    "rest": r"\brest(?:ful)?\b",
    "microservices": r"\bmicroservices?\b",
    "pandas": r"\bpandas\b",
    "numpy": r"\bnumpy\b",
    "tensorflow": r"\btensorflow\b",
    "pytorch": r"\bpytorch\b",
    "machine_learning": r"\bmachine learning\b|\bml\b",
    "data_analysis": r"\bdata analysis\b",
}


def call_llm(
    prompt: str,
    *,
    response_model: type[T],
    user_settings: object | None = None,
    temperature: float | None = None,
) -> T:
    """Temporary structured extractor until provider-backed LLM routing lands."""
    del user_settings, temperature
    from app.services.scrapers.adapters.generic import _heuristic_extract_jobs

    field_names = set(response_model.model_fields)
    if field_names == {"skills"}:
        payload = {"skills": _heuristic_extract_skills(prompt)}
        return response_model.model_validate(payload)

    payload = {"jobs": _heuristic_extract_jobs(prompt)}
    return response_model.model_validate(payload)


def _heuristic_extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    skills = [name for name, pattern in _SKILL_PATTERNS.items() if re.search(pattern, lowered)]
    return skills[:15]
