from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Date, Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models.job_posting import JobPosting
from app.db.models.user import User
from app.schemas.job import JobListParams, JobListRead, JobPostingRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _apply_job_filters(statement, params: JobListParams, *, dialect_name: str):
    statement = statement.where(JobPosting.is_active.is_(True))

    if params.source:
        statement = statement.where(func.lower(JobPosting.source) == params.source.lower())

    if params.work_type:
        if dialect_name == "postgresql":
            statement = statement.where(JobPosting.work_type.any(params.work_type))
        else:
            statement = statement.where(cast(JobPosting.work_type, Text).ilike(f"%{params.work_type}%"))

    if params.location:
        statement = statement.where(JobPosting.location.ilike(f"%{params.location}%"))

    if params.posted_after:
        statement = statement.where(func.cast(JobPosting.posted_at, Date) >= params.posted_after)

    if params.search:
        if dialect_name == "postgresql":
            query = func.plainto_tsquery("english", params.search)
            statement = statement.where(JobPosting.search_vector.op("@@")(query))
        else:
            like_term = f"%{params.search}%"
            statement = statement.where(
                or_(
                    JobPosting.title.ilike(like_term),
                    JobPosting.company_name_raw.ilike(like_term),
                    JobPosting.description.ilike(like_term),
                    JobPosting.location.ilike(like_term),
                )
            )

    return statement


def _apply_job_ordering(statement, params: JobListParams, *, dialect_name: str):
    if params.search and dialect_name == "postgresql":
        query = func.plainto_tsquery("english", params.search)
        return statement.order_by(
            func.ts_rank(JobPosting.search_vector, query).desc(),
            JobPosting.scraped_at.desc(),
            JobPosting.id.desc(),
        )

    return statement.order_by(JobPosting.scraped_at.desc(), JobPosting.id.desc())


@router.get("/", response_model=JobListRead)
async def list_jobs(
    source: Annotated[str | None, Query()] = None,
    work_type: Annotated[str | None, Query()] = None,
    location: Annotated[str | None, Query()] = None,
    posted_after: Annotated[date | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JobListRead:
    del current_user

    params = JobListParams(
        source=source,
        work_type=work_type,
        location=location,
        posted_after=posted_after,
        search=search,
        skip=skip,
        limit=limit,
    )
    dialect_name = db.bind.dialect.name if db.bind is not None else "postgresql"

    base_statement = _apply_job_filters(select(JobPosting), params, dialect_name=dialect_name)
    count_statement = _apply_job_filters(
        select(func.count()).select_from(JobPosting),
        params,
        dialect_name=dialect_name,
    )

    total = int((await db.execute(count_statement)).scalar_one())
    result = await db.execute(
        _apply_job_ordering(base_statement, params, dialect_name=dialect_name).offset(params.skip).limit(params.limit)
    )
    jobs = result.scalars().all()

    return JobListRead(
        total=total,
        items=[JobPostingRead.model_validate(job) for job in jobs],
        skip=params.skip,
        limit=params.limit,
    )


@router.get("/{job_id}", response_model=JobPostingRead)
async def read_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JobPostingRead:
    del current_user

    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == job_id,
            JobPosting.is_active.is_(True),
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return JobPostingRead.model_validate(job)
