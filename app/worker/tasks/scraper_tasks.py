from __future__ import annotations

import logging

from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services.scrapers.service import load_scrape_cursor, persist_scraped_jobs, resolve_scraper_adapter, update_scrape_action_log

logger = logging.getLogger(__name__)


async def scrape_job_board(
    ctx: dict[str, object],
    url: str,
    source_type: str,
    user_id: int | None = None,
    keywords: list[str] | None = None,
) -> dict[str, object]:
    # ATLAS-0 keeps scraping on ARQ so APScheduler remains a thin orchestrator.
    adapter = resolve_scraper_adapter(url=url, source_type=source_type)
    task_id = str(ctx.get("job_id")) if ctx.get("job_id") else None

    async with AsyncSessionLocal() as session:
        try:
            crawl_state = await load_scrape_cursor(
                db=session,
                source_type=source_type,
                url=url,
                user_id=user_id,
            )
            crawl_result = await adapter.crawl_jobs(
                url,
                keywords=keywords,
                cursor=crawl_state,
            )
            jobs = crawl_result.jobs
            saved_count, skipped_count, new_job_ids = await persist_scraped_jobs(
                db=session,
                jobs=jobs,
                source_type=source_type,
                user_id=user_id,
            )
            if new_job_ids:
                await extract_skills_for_new_jobs(session, new_job_ids)
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
                    "crawl_state": {
                        "next_page_url": crawl_result.next_page_url,
                        "pending_detail_urls": crawl_result.pending_detail_urls,
                    },
                    "pages_scanned": crawl_result.pages_scanned,
                    "detail_pages_scanned": crawl_result.detail_pages_scanned,
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


class SkillsExtraction(BaseModel):
    skills: list[str] = Field(
        default_factory=list,
        description="Normalized skill tags extracted from the job description.",
    )


async def extract_skills_for_new_jobs(db: AsyncSession, job_ids: list[int]) -> None:
    from app.db.models.job_posting import JobPosting
    from app.services.llm import call_llm

    for job_id in job_ids:
        result = await db.execute(
            select(JobPosting.description).where(JobPosting.id == job_id)
        )
        description = result.scalar_one_or_none()
        if not description:
            continue
        try:
            output = call_llm(
                prompt=f"Extract technical skills from this job description:\n\n{description[:3000]}",
                response_model=SkillsExtraction,
                temperature=0.0,
            )
            await db.execute(
                update(JobPosting)
                .where(JobPosting.id == job_id)
                .values(skills_required=output.skills)
            )
        except Exception as exc:  # pragma: no cover - defensive against provider wiring changes
            logger.warning("Skills extraction failed for job %s: %s", job_id, exc)
    await db.commit()
