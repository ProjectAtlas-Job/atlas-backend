import json
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy import Date, Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_active_user, get_db, get_redis
from app.db.models.job_posting import JobPosting
from app.db.models.user import User
from app.schemas.job import JobListParams, JobListRead, JobMatchListRead, JobMatchRead, JobPostingRead
from app.schemas.scraper import (
    ManualJobSubmissionDuplicateResponse,
    ManualJobSubmissionQueuedResponse,
    ManualJobSubmissionRequest,
)
from app.services.matching.engine import (
    CACHE_TTL_SECONDS,
    get_job_matches,
    get_match_threshold,
    make_job_matches_cache_key,
    serialize_match,
    serialize_cached_matches_payload,
)
from app.services.scrapers.service import enqueue_scrape_job

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


@router.get("/matches", response_model=JobMatchListRead)
async def list_job_matches(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
) -> JobMatchListRead:
    threshold = await get_match_threshold(current_user.id, db)
    cache_key = make_job_matches_cache_key(current_user.id)
    cached_payload = await redis.get(cache_key)
    if cached_payload:
        payload = json.loads(cached_payload)
        return JobMatchListRead(
            items=[JobMatchRead.model_validate(item) for item in payload["items"]],
            cached=True,
            generated_at=payload["generated_at"],
        )

    results = await get_job_matches(current_user.id, db, threshold=threshold)
    generated_at = datetime.now(UTC)
    if results:
        await redis.set(
            cache_key,
            serialize_cached_matches_payload(results, generated_at=generated_at),
            ex=CACHE_TTL_SECONDS,
        )

    return JobMatchListRead(
        items=[JobMatchRead.model_validate(serialize_match(result)) for result in results],
        cached=False,
        generated_at=generated_at,
    )


@router.post(
    "/manual",
    response_model=ManualJobSubmissionQueuedResponse | ManualJobSubmissionDuplicateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_manual_job(
    payload: ManualJobSubmissionRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    arq_pool: object = Depends(get_arq_pool),
) -> ManualJobSubmissionQueuedResponse | ManualJobSubmissionDuplicateResponse:
    source_url = str(payload.url)
    result = await db.execute(select(JobPosting).where(JobPosting.source_url == source_url))
    existing_job = result.scalar_one_or_none()

    if existing_job is not None:
        existing_job.last_checked_at = datetime.now(UTC)
        await db.commit()
        response.status_code = status.HTTP_200_OK
        return ManualJobSubmissionDuplicateResponse(status="already_exists", job_id=existing_job.id)

    await enqueue_scrape_job(
        arq_pool=arq_pool,
        db=db,
        current_user=current_user,
        url=source_url,
        source_type="manual",
    )
    return ManualJobSubmissionQueuedResponse(
        status="queued",
        message="Job is being fetched and parsed",
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
