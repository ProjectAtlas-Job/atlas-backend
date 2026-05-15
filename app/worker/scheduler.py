from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update

from app.core.constants import MAJOR_JOB_BOARDS, MINOR_JOB_BOARDS
from app.db.models.job_posting import JobPosting
from app.db.models.user_settings import UserSettings
from app.db.session import AsyncSessionLocal

try:
    from app.db.models.api_key_pool import ApiKeyPool
except ImportError:  # pragma: no cover - Sprint 2 schema does not include this table yet.
    ApiKeyPool = None


class ArqPoolProtocol(Protocol):
    async def enqueue_job(self, name: str, **kwargs: object) -> None: ...


logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone=UTC)
_arq_pool: ArqPoolProtocol | None = None


def bind_arq_pool(arq_pool: ArqPoolProtocol) -> None:
    global _arq_pool
    _arq_pool = arq_pool


def clear_arq_pool() -> None:
    global _arq_pool
    _arq_pool = None


async def _enqueue_scrape_job(*, url: str, source_type: str, user_id: int | None = None) -> None:
    if _arq_pool is None:
        logger.warning("[CRON] skipped enqueue for %s because ARQ pool is not bound", source_type)
        return

    payload: dict[str, Any] = {"url": url, "source_type": source_type}
    if user_id is not None:
        payload["user_id"] = user_id
    await _arq_pool.enqueue_job("scrape_job_board", **payload)


@scheduler.scheduled_job("interval", hours=4, id="scrape_major_boards")
async def scrape_major_boards() -> None:
    logger.info("[CRON] scrape_major_boards fired at %s", datetime.now(UTC).isoformat())
    for board in MAJOR_JOB_BOARDS:
        await _enqueue_scrape_job(url=board["url"], source_type=board["source_type"])


@scheduler.scheduled_job("interval", hours=12, id="scrape_minor_boards")
async def scrape_minor_boards() -> None:
    logger.info("[CRON] scrape_minor_boards fired at %s", datetime.now(UTC).isoformat())
    for board in MINOR_JOB_BOARDS:
        await _enqueue_scrape_job(url=board["url"], source_type=board["source_type"])


@scheduler.scheduled_job("interval", hours=4, id="user_configured_scraping")
async def user_configured_scraping() -> None:
    if _arq_pool is None:
        return
    logger.info("[CRON] user_configured_scraping fired at %s", datetime.now(UTC).isoformat())

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserSettings))
        for settings in result.scalars().all():
            if not settings.scrape_urls:
                continue
            for entry in settings.scrape_urls:
                if not isinstance(entry, dict):
                    continue
                url = entry.get("url")
                if not isinstance(url, str) or not url.strip():
                    continue
                await _enqueue_scrape_job(
                    url=url,
                    source_type="scraper",
                    user_id=settings.user_id,
                )


@scheduler.scheduled_job("cron", hour=0, minute=1, id="rotate_api_keys")
async def rotate_api_keys() -> None:
    if ApiKeyPool is None:
        return

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ApiKeyPool).values(
                daily_used=0,
                last_reset_at=datetime.now(UTC).date(),
            )
        )
        await db.commit()


@scheduler.scheduled_job("cron", hour=3, minute=0, id="deactivate_stale_jobs")
async def deactivate_stale_jobs() -> None:
    cutoff = datetime.now(UTC) - timedelta(days=14)

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(JobPosting)
            .where(JobPosting.last_checked_at.is_not(None))
            .where(JobPosting.last_checked_at < cutoff)
            .values(is_active=False)
        )
        await db.commit()
