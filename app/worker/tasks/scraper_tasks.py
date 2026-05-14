from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models.job_posting import JobPosting
from app.db.models.user_job_save import UserJobSave
from app.db.session import AsyncSessionLocal
from app.services.resume.embedder import embed
from app.services.scrapers import get_adapter_for_source
from app.services.scrapers.base import JobItem
from app.services.scrapers.utils import parse_posted_at


async def scrape_job_board(
    ctx: dict[str, object],
    url: str,
    source_type: str,
    user_id: int | None = None,
) -> dict[str, object]:
    del ctx
    adapter = get_adapter_for_source(source_type)
    jobs = await adapter.fetch_jobs(url)

    saved_count = 0
    skipped_count = 0
    for job in jobs:
        saved = await embed_and_save(job, source_type=source_type, user_id=user_id)
        if saved:
            saved_count += 1
        else:
            skipped_count += 1

    return {"saved_count": saved_count, "skipped_count": skipped_count, "source_type": source_type}


async def embed_and_save(job_item: JobItem, source_type: str, user_id: int | None = None) -> bool:
    if not job_item.source_url or not job_item.title or not job_item.company:
        return False

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(JobPosting).where(JobPosting.source_url == job_item.source_url)
        )
        existing = result.scalar_one_or_none()
        now = datetime.now(UTC)
        embedding = await asyncio.to_thread(embed, f"{job_item.title}\n\n{job_item.description[:2000]}")

        if existing is None:
            posting = JobPosting(
                company_id=None,
                company_name_raw=job_item.company,
                title=job_item.title,
                description=job_item.description,
                location=job_item.location,
                work_type=job_item.work_type,
                salary_min=job_item.salary_min,
                salary_max=job_item.salary_max,
                experience_required=None,
                skills_required=None,
                source=source_type,
                source_url=job_item.source_url,
                embedding=embedding,
                is_active=True,
                posted_at=parse_posted_at(job_item.posted_at),
                scraped_at=now,
                last_checked_at=now,
            )
            session.add(posting)
            await session.flush()
        else:
            posting = existing
            posting.company_name_raw = job_item.company
            posting.title = job_item.title
            posting.description = job_item.description
            posting.location = job_item.location
            posting.work_type = job_item.work_type
            posting.salary_min = job_item.salary_min
            posting.salary_max = job_item.salary_max
            posting.source = source_type
            posting.embedding = embedding
            posting.is_active = True
            posting.posted_at = parse_posted_at(job_item.posted_at)
            posting.last_checked_at = now

        if user_id is not None:
            save_result = await session.execute(
                select(UserJobSave).where(
                    UserJobSave.user_id == user_id,
                    UserJobSave.job_id == posting.id,
                )
            )
            save = save_result.scalar_one_or_none()
            if save is None:
                session.add(UserJobSave(user_id=user_id, job_id=posting.id))

        await session.commit()
    return True
