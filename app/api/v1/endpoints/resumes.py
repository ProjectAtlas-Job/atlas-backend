from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_active_user, get_db, get_redis
from app.db.models.resume import Resume
from app.db.models.user import User
from app.schemas.resume import ResumeRead, ResumeStatusRead, ResumeUpdate
from app.services.matching.engine import make_job_matches_cache_key
from app.services.profile.completeness import refresh_profile_completeness
from app.services.resume.service import (
    enqueue_resume_processing,
    get_resume_extension,
    normalize_resume_label,
    upload_resume_to_storage,
    validate_resume_upload,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])


async def _get_user_resume(*, db: AsyncSession, user_id: int, resume_id: int) -> Resume:
    result = await db.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == user_id,
            Resume.deleted_at.is_(None),
        )
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return resume


@router.post("/upload", response_model=ResumeRead, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(
    resume_file: Annotated[UploadFile, File(...)],
    label: Annotated[str | None, Form()] = None,
    db: AsyncSession = Depends(get_db),
    arq_pool=Depends(get_arq_pool),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
) -> ResumeRead:
    file_bytes = await resume_file.read()
    extension = get_resume_extension(resume_file.filename)
    filename = resume_file.filename or f"resume.{extension}"
    validate_resume_upload(file_bytes, extension)
    storage_path = await upload_resume_to_storage(
        user_id=current_user.id,
        extension=extension,
        file_bytes=file_bytes,
    )

    active_resume_count = await db.scalar(
        select(func.count()).select_from(Resume).where(
            Resume.user_id == current_user.id,
            Resume.deleted_at.is_(None),
        )
    )
    resume = Resume(
        user_id=current_user.id,
        filename=filename,
        format=extension,
        label=normalize_resume_label(label),
        file_data=file_bytes,
        storage_path=storage_path,
        status="pending",
        is_primary=(active_resume_count or 0) == 0,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    try:
        await enqueue_resume_processing(
            arq_pool=arq_pool,
            resume_id=resume.id,
            file_bytes=file_bytes,
            filename=filename,
        )
    except Exception:
        logger.exception("Resume processing could not be started for resume_id={}", resume.id)
        resume.status = "error"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume was uploaded but processing could not be started.",
        )

    await redis.delete(make_job_matches_cache_key(current_user.id))
    await arq_pool.enqueue_job("refresh_job_matches", user_id=current_user.id)

    return ResumeRead.model_validate(resume)


@router.get("/", response_model=list[ResumeRead])
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ResumeRead]:
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == current_user.id, Resume.deleted_at.is_(None))
        .order_by(Resume.created_at.desc(), Resume.id.desc())
    )
    return [ResumeRead.model_validate(resume) for resume in result.scalars().all()]


@router.get("/{resume_id}/status", response_model=ResumeStatusRead)
async def get_resume_status(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ResumeStatusRead:
    resume = await _get_user_resume(db=db, user_id=current_user.id, resume_id=resume_id)
    return ResumeStatusRead(
        status=resume.status,
        structural_score=resume.structural_score,
        semantic_score=resume.semantic_score,
        ats_score=resume.ats_score,
    )


@router.put("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    resume_id: int,
    payload: ResumeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ResumeRead:
    resume = await _get_user_resume(db=db, user_id=current_user.id, resume_id=resume_id)

    if "label" in payload.model_fields_set:
        resume.label = payload.label

    if "is_primary" in payload.model_fields_set and payload.is_primary is not None:
        if payload.is_primary:
            await db.execute(
                update(Resume)
                .where(
                    Resume.user_id == current_user.id,
                    Resume.deleted_at.is_(None),
                    Resume.id != resume.id,
                )
                .values(is_primary=False)
            )
        resume.is_primary = payload.is_primary

    await db.commit()
    await db.refresh(resume)
    return ResumeRead.model_validate(resume)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    resume = await _get_user_resume(db=db, user_id=current_user.id, resume_id=resume_id)
    resume.deleted_at = datetime.now(UTC)
    resume.is_primary = False
    await db.flush()
    await refresh_profile_completeness(db, user_id=current_user.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
