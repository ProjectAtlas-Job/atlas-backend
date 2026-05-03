import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.constants import REFRESH_TOKEN_COOKIE_NAME
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.db.models.user_settings import UserSettings
from app.schemas.auth import (
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserRead,
    VerifyEmailRequest,
)
from app.services.email import system_smtp

router = APIRouter(prefix="/auth", tags=["auth"])

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _refresh_token_ttl_seconds() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


def _set_refresh_cookie(response: Response, refresh_token: str, max_age: int) -> None:
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=max_age,
    )


async def _issue_refresh_token(user_id: int) -> str:
    refresh_token = str(uuid4())
    await redis_client.setex(f"refresh:{refresh_token}", _refresh_token_ttl_seconds(), str(user_id))
    return refresh_token


async def _create_default_settings(db: AsyncSession, user_id: int) -> None:
    db.add(UserSettings(user_id=user_id))


async def _send_verification_email(user: User) -> None:
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={user.email_verification_token}"
    await system_smtp.send_email(
        to=user.email,
        subject="Verify your Project Atlas email",
        body_html=f"<p>Verify your email by visiting <a href=\"{verification_link}\">{verification_link}</a>.</p>",
    )


async def _send_password_reset_email(user: User) -> None:
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={user.password_reset_token}"
    await system_smtp.send_email(
        to=user.email,
        subject="Reset your Project Atlas password",
        body_html=f"<p>Reset your password by visiting <a href=\"{reset_link}\">{reset_link}</a>.</p>",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    email = payload.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        email_verification_token=str(uuid4()),
    )

    db.add(user)
    await db.flush()
    await _create_default_settings(db, user.id)
    await db.commit()
    await db.refresh(user)
    asyncio.create_task(_send_verification_email(user))
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    email = form_data.username.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.is_email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user.")
    if not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    access_token = create_access_token(subject=str(user.id), email=user.email)
    refresh_token = await _issue_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token, _refresh_token_ttl_seconds())
    return Token(access_token=access_token, token_type="bearer")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> Response:
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if refresh_token:
        await redis_client.delete(f"refresh:{refresh_token}")
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value="",
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=0,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Token:
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token.")

    user_id = await redis_client.get(f"refresh:{refresh_token}")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    access_token = create_access_token(subject=str(user.id), email=user.email)
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserRead)
async def read_me(current_user: User = Depends(get_current_active_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/verify-email")
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await db.execute(select(User).where(User.email_verification_token == payload.token))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token.")

    user.is_email_verified = True
    user.email_verification_token = None
    await db.commit()
    return {"status": "verified"}


@router.post("/resend-verification")
async def resend_verification(
    payload: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    current_user = result.scalar_one_or_none()
    if current_user is None:
        return {"status": "verification_resent"}
    if current_user.is_email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already verified.")

    current_user.email_verification_token = str(uuid4())
    await db.commit()
    await db.refresh(current_user)
    asyncio.create_task(_send_verification_email(current_user))
    return {"status": "verification_resent"}


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is not None:
        user.password_reset_token = str(uuid4())
        user.password_reset_expires = datetime.now(UTC) + timedelta(hours=1)
        await db.commit()
        await db.refresh(user)
        asyncio.create_task(_send_password_reset_email(user))
    return {"status": "ok"}


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await db.execute(
        select(User).where(
            User.password_reset_token == payload.token,
            User.password_reset_expires.is_not(None),
            User.password_reset_expires > datetime.now(UTC),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.commit()
    return {"status": "password_reset"}


@router.get("/google/connect")
async def google_connect() -> RedirectResponse:
    params = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_callback(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        google_tokens = token_response.json()

        userinfo_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {google_tokens['access_token']}"},
        )
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()

    email = userinfo["email"].lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            full_name=userinfo.get("name"),
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()
        await _create_default_settings(db, user.id)
        await db.commit()
    else:
        user.full_name = user.full_name or userinfo.get("name")
        user.is_email_verified = True
        await db.commit()

    await db.refresh(user)
    access_token = create_access_token(subject=str(user.id), email=user.email)
    refresh_token = await _issue_refresh_token(user.id)
    redirect = RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard?access_token={access_token}")
    _set_refresh_cookie(redirect, refresh_token, _refresh_token_ttl_seconds())
    return redirect


@router.get("/github/connect")
async def github_connect() -> RedirectResponse:
    params = urlencode(
        {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "scope": "read:user public_repo",
        }
    )
    return RedirectResponse(url=f"https://github.com/login/oauth/authorize?{params}")


@router.get("/github/callback")
async def github_callback(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
        )
        token_response.raise_for_status()
        github_tokens = token_response.json()

        profile_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_tokens['access_token']}",
            },
        )
        profile_response.raise_for_status()
        github_user = profile_response.json()

        email_response = await client.get(
            "https://api.github.com/user/emails",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_tokens['access_token']}",
            },
        )
        email_response.raise_for_status()
        github_emails = email_response.json()

    primary_email = next((item["email"] for item in github_emails if item.get("primary")), None)
    if not primary_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub account has no primary email.")

    email = primary_email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            full_name=github_user.get("name"),
            github_username=github_user.get("login"),
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()
        await _create_default_settings(db, user.id)
        await db.commit()
    else:
        user.github_username = github_user.get("login")
        if github_user.get("name") and not user.full_name:
            user.full_name = github_user.get("name")
        await db.commit()

    await db.refresh(user)
    access_token = create_access_token(subject=str(user.id), email=user.email)
    refresh_token = await _issue_refresh_token(user.id)
    redirect = RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard?access_token={access_token}")
    _set_refresh_cookie(redirect, refresh_token, _refresh_token_ttl_seconds())
    return redirect
