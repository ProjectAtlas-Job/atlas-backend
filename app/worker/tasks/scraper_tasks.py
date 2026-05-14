from __future__ import annotations

from app.db.session import AsyncSessionLocal
from app.services.scrapers.service import persist_scraped_jobs, resolve_scraper_adapter, update_scrape_action_log


async def scrape_job_board(
    ctx: dict[str, object],
    url: str,
    source_type: str,
    user_id: int | None = None,
    keywords: list[str] | None = None,
) -> dict[str, object]:
    adapter = resolve_scraper_adapter(url=url, source_type=source_type)
    task_id = str(ctx.get("job_id")) if ctx.get("job_id") else None

    async with AsyncSessionLocal() as session:
        try:
            jobs = await adapter.fetch_jobs(url, keywords=keywords)
            saved_count, skipped_count = await persist_scraped_jobs(
                db=session,
                jobs=jobs,
                source_type=source_type,
                user_id=user_id,
            )
            await update_scrape_action_log(
                db=session,
                user_id=user_id,
                task_id=task_id,
                status="success",
                message=None,
                metadata_updates={
                    "task_id": task_id,
                    "url": url,
                    "source_type": source_type,
                    "keywords": keywords or [],
                    "saved_count": saved_count,
                    "skipped_count": skipped_count,
                },
            )
        except Exception as exc:
            await update_scrape_action_log(
                db=session,
                user_id=user_id,
                task_id=task_id,
                status="failed",
                message=str(exc),
                metadata_updates={
                    "task_id": task_id,
                    "url": url,
                    "source_type": source_type,
                    "keywords": keywords or [],
                },
            )
            raise

    return {"saved_count": saved_count, "skipped_count": skipped_count, "source_type": source_type}
