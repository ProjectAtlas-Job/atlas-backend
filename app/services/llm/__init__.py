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

    if field_names == {
        "skills",
        "recent_role",
        "education",
        "top_projects",
        "certifications",
        "experience_years",
        "ats_score",
        "ats_reasoning",
    }:
        payload = _heuristic_extract_resume(prompt)
        return response_model.model_validate(payload)

    payload = {"jobs": _heuristic_extract_jobs(prompt)}
    return response_model.model_validate(payload)


def _heuristic_extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    skills = [name for name, pattern in _SKILL_PATTERNS.items() if re.search(pattern, lowered)]
    return skills[:15]


def _heuristic_extract_resume(text: str) -> dict[str, object]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lowered = text.lower()
    skills = _heuristic_extract_skills(text)

    recent_role = ""
    for line in lines:
        if len(line.split()) >= 2 and not line.lower().startswith(("analyse this resume", "resume text:", "extract:")):
            recent_role = line[:120]
            break

    education = ""
    for line in lines:
        if "university" in line.lower() or "college" in line.lower() or "b.tech" in line.lower() or "bachelor" in line.lower():
            education = line[:160]
            break

    top_projects = [line[:120] for line in lines if "project" in line.lower()][:3]

    certifications = [
        line[:120]
        for line in lines
        if "certif" in line.lower() or "coursera" in line.lower() or "udemy" in line.lower()
    ][:5]

    experience_years = 0
    years_match = re.search(r"(\d+)\+?\s+years?", lowered)
    if years_match:
        experience_years = int(years_match.group(1))

    ats_score = 55.0
    score = ats_score
    if re.search(r"\bexperience\b", lowered):
        score += 10
    if re.search(r"\beducation\b", lowered):
        score += 10
    if re.search(r"\bskills?\b", lowered):
        score += 10
    if re.search(r"\bproject[s]?\b", lowered):
        score += 5
    if re.search(r"\bachieved|\bimproved|\bincreased|\breduced|\bbuilt|\bdelivered", lowered):
        score += 5
    if re.search(r"\d+%", lowered) or re.search(r"\b\d+\b", lowered):
        score += 5
    ats_score = float(max(0, min(100, score)))

    return {
        "skills": skills,
        "recent_role": recent_role or "Not clearly identified",
        "education": education or "Not clearly identified",
        "top_projects": top_projects,
        "certifications": certifications,
        "experience_years": experience_years,
        "ats_score": ats_score,
        "ats_reasoning": "Heuristic ATS estimate based on section structure, action language, and measurable details.",
    }
