from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models.user import User
from app.schemas.auth import UserRead
from app.schemas.user import ProfileCompletenessRead, UserUpdate
from app.services.profile.completeness import get_profile_completeness, refresh_profile_completeness

router = APIRouter(prefix="/users", tags=["users"])


@router.put("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserRead:
    user = current_user

    for field_name in payload.model_fields_set:
        setattr(user, field_name, getattr(payload, field_name))

    await db.flush()
    user, _, _ = await refresh_profile_completeness(db, user_id=user.id)

    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.get("/me/profile-completeness", response_model=ProfileCompletenessRead)
async def read_profile_completeness(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProfileCompletenessRead:
    _, score, missing = await get_profile_completeness(db, user_id=current_user.id)
    return ProfileCompletenessRead(score=score, missing=missing)
