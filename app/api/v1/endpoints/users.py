from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user, get_db
from app.db.models.resume import Resume
from app.db.models.user import User
from app.schemas.auth import UserRead
from app.schemas.user import ProfileCompletenessRead, UserUpdate
from app.services.profile.completeness import compute_completeness

router = APIRouter(prefix="/users", tags=["users"])


async def _get_user_with_settings(*, db: AsyncSession, user_id: int) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.settings)).where(User.id == user_id)
    )
    return result.scalar_one()


async def _has_completed_resume(*, db: AsyncSession, user_id: int) -> bool:
    result = await db.execute(
        select(Resume.id).where(
            Resume.user_id == user_id,
            Resume.status == "completed",
            Resume.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None


async def _build_completeness_payload(*, db: AsyncSession, user: User) -> ProfileCompletenessRead:
    has_completed_resume = await _has_completed_resume(db=db, user_id=user.id)
    gmail_connected = bool(user.settings and user.settings.gmail_access_token_encrypted)
    score, missing = compute_completeness(
        user=user,
        has_completed_resume=has_completed_resume,
        gmail_connected=gmail_connected,
    )
    return ProfileCompletenessRead(score=score, missing=missing)


@router.put("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserRead:
    user = await _get_user_with_settings(db=db, user_id=current_user.id)

    for field_name in payload.model_fields_set:
        setattr(user, field_name, getattr(payload, field_name))

    completeness = await _build_completeness_payload(db=db, user=user)
    user.profile_completeness = completeness.score

    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.get("/me/profile-completeness", response_model=ProfileCompletenessRead)
async def read_profile_completeness(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProfileCompletenessRead:
    user = await _get_user_with_settings(db=db, user_id=current_user.id)
    return await _build_completeness_payload(db=db, user=user)
