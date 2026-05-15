from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from arq.jobs import Job
from sqlalchemy import desc, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.action_log import ActionLog
from app.db.models.company import Company
from app.db.models.job_posting import JobPosting
from app.db.models.user import User
from app.db.models.user_job_save import UserJobSave
from app.services.resume.embedder import embed
from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, parse_posted_at


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
    job_kwargs: dict[str, object] = {
        "url": url,
        "source_type": source_type,
        "user_id": current_user.id,
        "_job_id": task_id,
    }
    if keywords:
        job_kwargs["keywords"] = keywords
    await arq_pool.enqueue_job("scrape_job_board", **job_kwargs)
    db.add(
        ActionLog(
            user_id=current_user.id,
            action_type="scraper",
            status="running",
            meta={
                "task_id": task_id,
                "url": url,
                "source_type": source_type,
                "keywords": keywords or [],
            },
        )
    )
    await db.commit()
    return task_id


def resolve_scraper_adapter(*, url: str, source_type: str) -> BaseJobAdapter:
    from app.services.scrapers import get_adapter_for_source, get_adapter_for_url

    normalized_source = clean_text(source_type).lower()
    if normalized_source and normalized_source not in {"manual", "scraper"}:
        adapter = get_adapter_for_source(normalized_source)
        if adapter.source_name != "scraper":
            return adapter
    return get_adapter_for_url(url)


async def persist_scraped_jobs(
    *,
    db: AsyncSession,
    jobs: list[JobItem],
    source_type: str,
    user_id: int | None = None,
) -> tuple[int, int, list[int]]:
    saved_count = 0
    skipped_count = 0
    new_job_ids: list[int] = []

    for job_item in jobs:
        if not job_item.source_url or not job_item.title or not job_item.company:
            skipped_count += 1
            continue

        posting, inserted = await _upsert_job_posting(
            db=db,
            job_item=job_item,
            source_type=source_type,
        )
        if inserted:
            saved_count += 1
            new_job_ids.append(posting.id)

        if user_id is not None:
            save_result = await db.execute(
                select(UserJobSave).where(
                    UserJobSave.user_id == user_id,
                    UserJobSave.job_id == posting.id,
                )
            )
            save = save_result.scalar_one_or_none()
            if save is None:
                db.add(UserJobSave(user_id=user_id, job_id=posting.id))

    await db.commit()
    return saved_count, skipped_count, new_job_ids


async def update_scrape_action_log(
    *,
    db: AsyncSession,
    status: str,
    message: str | None,
    user_id: int | None = None,
    task_id: str | None = None,
    metadata_updates: dict[str, Any] | None = None,
) -> None:
    log = await _find_scraper_action_log(db=db, user_id=user_id, task_id=task_id)
    if log is None:
        db.add(
            ActionLog(
                user_id=user_id,
                action_type="scraper",
                status=status,
                message=message,
                meta=metadata_updates,
            )
        )
        await db.commit()
        return

    log.status = status
    log.message = message
    existing_meta = _action_log_meta(log)
    log.meta = {**existing_meta, **(metadata_updates or {})}
    await db.commit()


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
        task_id = _action_log_meta(log).get("task_id")
        if not isinstance(task_id, str) or not task_id:
            continue
        job = Job(task_id, redis=arq_pool)
        await job.abort()
        log.status = "cancelled"
    await db.commit()
    return sum(1 for log in logs if log.status == "cancelled")


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
        ).order_by(ActionLog.created_at.desc(), ActionLog.id.desc())
    )
    return list(result.scalars().all())


def _action_log_meta(log: ActionLog) -> dict[str, Any]:
    if isinstance(log.meta, dict):
        return log.meta
    return {}


async def _find_scraper_action_log(
    *,
    db: AsyncSession,
    user_id: int | None,
    task_id: str | None,
) -> ActionLog | None:
    statement = select(ActionLog).where(ActionLog.action_type == "scraper").order_by(
        desc(ActionLog.created_at),
        desc(ActionLog.id),
    )
    if user_id is not None:
        statement = statement.where(ActionLog.user_id == user_id)

    result = await db.execute(statement)
    logs = result.scalars().all()
    if task_id:
        for log in logs:
            if _action_log_meta(log).get("task_id") == task_id:
                return log

    return logs[0] if logs else None


async def resolve_company_id(db: AsyncSession, company_name_raw: str) -> int | None:
    normalized = clean_text(company_name_raw).lower()
    if not normalized:
        return None
    result = await db.execute(
        select(Company.id)
        .where(func.lower(Company.name) == normalized)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def upsert_company_stub(db: AsyncSession, company_name: str) -> int | None:
    normalized = clean_text(company_name)
    if not normalized:
        return None

    existing_id = await resolve_company_id(db, normalized)
    if existing_id is not None:
        return existing_id

    db.add(
        Company(
            name=normalized,
            is_verified=False,
            last_enriched_at=None,
        )
    )
    await db.flush()
    return await resolve_company_id(db, normalized)


async def _upsert_job_posting(
    *,
    db: AsyncSession,
    job_item: JobItem,
    source_type: str,
) -> tuple[JobPosting, bool]:
    source = clean_text(source_type) or "scraper"
    now = datetime.now(UTC)
    company_id = await resolve_company_id(db, job_item.company)
    if company_id is None:
        company_id = await upsert_company_stub(db, job_item.company)
    embedding = await asyncio.to_thread(
        embed,
        f"{job_item.title} {job_item.company} {job_item.description[:2000]}",
    )
    values = {
        "company_id": company_id,
        "company_name_raw": job_item.company,
        "title": job_item.title,
        "description": job_item.description,
        "location": job_item.location,
        "work_type": job_item.work_type,
        "salary_min": job_item.salary_min,
        "salary_max": job_item.salary_max,
        "experience_required": clean_text(job_item.experience_required) or None,
        "skills_required": [],
        "source": source,
        "source_url": job_item.source_url,
        "embedding": embedding,
        "is_active": True,
        "posted_at": parse_posted_at(job_item.posted_at),
        "last_checked_at": now,
    }
    dialect_name = db.bind.dialect.name if db.bind is not None else ""

    if dialect_name == "postgresql":
        insert_stmt = pg_insert(JobPosting).values(**values)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[JobPosting.source_url],
            set_={
                "company_name_raw": insert_stmt.excluded.company_name_raw,
                "title": insert_stmt.excluded.title,
                "description": insert_stmt.excluded.description,
                "location": insert_stmt.excluded.location,
                "work_type": insert_stmt.excluded.work_type,
                "salary_min": insert_stmt.excluded.salary_min,
                "salary_max": insert_stmt.excluded.salary_max,
                "experience_required": func.coalesce(
                    insert_stmt.excluded.experience_required,
                    JobPosting.experience_required,
                ),
                "company_id": func.coalesce(insert_stmt.excluded.company_id, JobPosting.company_id),
                "source": insert_stmt.excluded.source,
                "embedding": insert_stmt.excluded.embedding,
                "is_active": True,
                "posted_at": insert_stmt.excluded.posted_at,
                "last_checked_at": text("now()"),
            },
        ).returning(JobPosting, text("xmax = 0 AS inserted"))
        result = await db.execute(upsert_stmt)
        row = result.one()
        return row[0], bool(row[1])

    result = await db.execute(select(JobPosting).where(JobPosting.source_url == job_item.source_url))
    posting = result.scalar_one_or_none()
    inserted = posting is None
    if posting is None:
        posting = JobPosting(**values, scraped_at=now)
        db.add(posting)
        await db.flush()
    else:
        posting.company_name_raw = job_item.company
        posting.title = job_item.title
        posting.description = job_item.description
        posting.location = job_item.location
        posting.work_type = job_item.work_type
        posting.salary_min = job_item.salary_min
        posting.salary_max = job_item.salary_max
        posting.experience_required = clean_text(job_item.experience_required) or posting.experience_required
        posting.company_id = company_id
        posting.source = source
        posting.embedding = embedding
        posting.is_active = True
        posting.posted_at = parse_posted_at(job_item.posted_at)
        posting.last_checked_at = now

    return posting, inserted
