import json
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy import Date, Text, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_active_user, get_db, get_redis
from app.db.models.job_posting import JobPosting
from app.db.models.user import User
from app.db.models.user_job_save import UserJobSave
from app.schemas.job import (
    JobListParams,
    JobListRead,
    JobMatchListRead,
    JobMatchRead,
    JobPostingRead,
    SavedJobItemRead,
    SavedJobListRead,
    UserJobSaveCreate,
    UserJobSaveRead,
    UserJobSaveUpdate,
)
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


async def _get_job_or_404(job_id: int, db: AsyncSession) -> JobPosting:
    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == job_id,
            JobPosting.is_active.is_(True),
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


async def _get_user_save(job_id: int, user_id: int, db: AsyncSession) -> UserJobSave | None:
    result = await db.execute(
        select(UserJobSave).where(
            UserJobSave.job_id == job_id,
            UserJobSave.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_cached_match_score(redis: Redis, user_id: int, job_id: int) -> float | None:
    cached_payload = await redis.get(make_job_matches_cache_key(user_id))
    if not cached_payload:
        return None

    payload = json.loads(cached_payload)
    for item in payload.get("items", []):
        job = item.get("job") if isinstance(item, dict) else None
        if isinstance(job, dict) and job.get("id") == job_id:
            score = item.get("match_score")
            return float(score) if isinstance(score, (int, float)) else None
    return None


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


@router.get("/saved", response_model=SavedJobListRead)
async def list_saved_jobs(
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SavedJobListRead:
    statement = (
        select(UserJobSave, JobPosting)
        .join(JobPosting, JobPosting.id == UserJobSave.job_id)
        .where(UserJobSave.user_id == current_user.id)
        .order_by(UserJobSave.created_at.desc(), UserJobSave.id.desc())
    )

    if status_filter is None:
        statement = statement.where(UserJobSave.status != "dismissed")
    else:
        statement = statement.where(UserJobSave.status == status_filter)

    rows = (await db.execute(statement)).all()
    return SavedJobListRead(
        items=[
            SavedJobItemRead(
                save=UserJobSaveRead.model_validate(row.UserJobSave),
                job=JobPostingRead.model_validate(row.JobPosting),
            )
            for row in rows
        ]
    )


@router.post("/{job_id}/save", response_model=UserJobSaveRead, status_code=status.HTTP_201_CREATED)
async def create_job_save(
    job_id: int,
    payload: UserJobSaveCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
) -> UserJobSaveRead:
    await _get_job_or_404(job_id, db)
    existing = await _get_user_save(job_id, current_user.id, db)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already saved. Use PUT to update.")

    save = UserJobSave(
        user_id=current_user.id,
        job_id=job_id,
        status=payload.status,
        notes=payload.notes,
        match_score=await _get_cached_match_score(redis, current_user.id, job_id),
    )
    db.add(save)
    await db.commit()
    await db.refresh(save)
    return UserJobSaveRead.model_validate(save)


@router.put("/{job_id}/save", response_model=UserJobSaveRead)
async def update_job_save(
    job_id: int,
    payload: UserJobSaveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserJobSaveRead:
    save = await _get_user_save(job_id, current_user.id, db)
    if save is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved job not found.")

    save.status = payload.status
    save.notes = payload.notes
    await db.commit()
    await db.refresh(save)
    return UserJobSaveRead.model_validate(save)


@router.delete("/{job_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_save(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    save = await _get_user_save(job_id, current_user.id, db)
    if save is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved job not found.")

    await db.execute(delete(UserJobSave).where(UserJobSave.id == save.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

    job = await _get_job_or_404(job_id, db)
    return JobPostingRead.model_validate(job)
