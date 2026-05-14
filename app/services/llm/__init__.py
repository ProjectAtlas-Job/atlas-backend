from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def call_llm(prompt: str, *, response_model: type[T]) -> T:
    """Temporary structured extractor until provider-backed LLM routing lands."""
    from app.services.scrapers.adapters.generic import _heuristic_extract_jobs

    payload = {"jobs": _heuristic_extract_jobs(prompt)}
    return response_model.model_validate(payload)
