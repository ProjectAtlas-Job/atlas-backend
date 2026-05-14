from __future__ import annotations

from uuid import uuid4

from arq.jobs import Job
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.action_log import ActionLog
from app.db.models.user import User


async def enqueue_scrape_job(
    *,
    arq_pool: object,
    db: AsyncSession,
    current_user: User,
    url: str,
    source_type: str,
    keywords: list[str] | None = None,
) -> str:
    task_id = str(uuid4())
    await arq_pool.enqueue_job(
        "scrape_job_board",
        url=url,
        source_type=source_type,
        user_id=current_user.id,
        keywords=keywords,
        _job_id=task_id,
    )
    db.add(
        ActionLog(
            user_id=current_user.id,
            action_type="scraper",
            task_id=task_id,
            url=url,
            status="running",
        )
    )
    await db.commit()
    return task_id


async def cancel_scraper_jobs(
    *,
    arq_pool: object,
    db: AsyncSession,
    current_user: User,
) -> int:
    result = await db.execute(
        select(ActionLog).where(
            ActionLog.user_id == current_user.id,
            ActionLog.action_type == "scraper",
            ActionLog.status == "running",
        )
    )
    logs = result.scalars().all()
    for log in logs:
        job = Job(log.task_id, redis=arq_pool)
        await job.abort()
        log.status = "cancelled"
    await db.commit()
    return len(logs)


async def list_running_scraper_jobs(
    *,
    db: AsyncSession,
    current_user: User,
) -> list[ActionLog]:
    result = await db.execute(
        select(ActionLog).where(
            ActionLog.user_id == current_user.id,
            ActionLog.action_type == "scraper",
            ActionLog.status == "running",
        ).order_by(ActionLog.started_at.desc(), ActionLog.id.desc())
    )
    return list(result.scalars().all())
