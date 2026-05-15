from __future__ import annotations

from app.db.session import AsyncSessionLocal
from app.services.matching.engine import (
    CACHE_TTL_SECONDS,
    get_job_matches,
    get_match_threshold,
    make_job_matches_cache_key,
    serialize_cached_matches_payload,
)


async def refresh_job_matches(ctx: dict[str, object], user_id: int) -> dict[str, object]:
    redis = ctx["redis"]

    async with AsyncSessionLocal() as db:
        threshold = await get_match_threshold(user_id, db)
        results = await get_job_matches(user_id, db, threshold=threshold)
        if results:
            await redis.set(
                make_job_matches_cache_key(user_id),
                serialize_cached_matches_payload(results),
                ex=CACHE_TTL_SECONDS,
            )
    return {"user_id": user_id, "count": len(results)}
