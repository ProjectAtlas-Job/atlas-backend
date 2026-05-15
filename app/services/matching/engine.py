from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.job_posting import JobPosting
from app.db.models.resume import Resume
from app.db.models.user_settings import UserSettings
from app.schemas.job import JobMatchRead, JobPostingRead

CACHE_TTL_SECONDS = 86400
DEFAULT_MATCH_THRESHOLD = 0.65


async def get_match_threshold(user_id: int, db: AsyncSession) -> float:
    result = await db.execute(select(UserSettings.match_threshold).where(UserSettings.user_id == user_id))
    threshold = result.scalar_one_or_none()
    return float(threshold) if threshold is not None else DEFAULT_MATCH_THRESHOLD


async def get_job_matches(
    user_id: int,
    db: AsyncSession,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    limit: int = 50,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Resume.embedding).where(
            Resume.user_id == user_id,
            Resume.is_primary.is_(True),
            Resume.deleted_at.is_(None),
        )
    )
    resume_embedding = result.scalar_one_or_none()
    if resume_embedding is None:
        return []

    distance = JobPosting.embedding.cosine_distance(resume_embedding)
    distance_threshold = 1.0 - threshold
    result = await db.execute(
        select(
            JobPosting,
            (1 - distance).label("match_score"),
        )
        .where(
            JobPosting.is_active.is_(True),
            JobPosting.embedding.is_not(None),
            distance <= distance_threshold,
        )
        .order_by(distance)
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "job": row.JobPosting,
            "match_score": round(float(row.match_score), 4),
        }
        for row in rows
    ]


def serialize_match(result: dict[str, Any]) -> dict[str, Any]:
    payload = JobMatchRead(
        job=JobPostingRead.model_validate(result["job"]),
        match_score=float(result["match_score"]),
    )
    return payload.model_dump(mode="json")


def serialize_cached_matches_payload(
    results: list[dict[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> str:
    timestamp = generated_at or datetime.now(UTC)
    payload = {
        "items": [serialize_match(result) for result in results],
        "generated_at": timestamp.isoformat(),
    }
    return json.dumps(payload)


def make_job_matches_cache_key(user_id: int) -> str:
    return f"user:{user_id}:job_matches"
