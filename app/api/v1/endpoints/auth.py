import asyncio
import secrets
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from html import escape
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.constants import REFRESH_TOKEN_COOKIE_NAME
from app.core.rate_limiter import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.db.models.user_settings import UserSettings
from app.schemas.auth import (
    ContactSupportRequest,
    EmailOtpRequest,
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserRead,
    VerifyEmailOtpRequest,
    VerifyEmailRequest,
)
from app.services.email.mail_service import mail_service
from app.services.email.templates import EmailContent, otp_email, password_reset_email, verification_email, welcome_email
from app.services.github.scanner import scan_github_repos
from app.services.profile.completeness import refresh_profile_completeness

router = APIRouter(prefix="/auth", tags=["auth"])

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

EMAIL_OTP_TTL_MINUTES = 10


def _refresh_token_ttl_seconds() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


def _set_refresh_cookie(response: Response, refresh_token: str, max_age: int) -> None:
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=settings.COOKIE_DOMAIN,
        max_age=max_age,
    )


def _require_email_service() -> None:
    if not settings.email_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured on the server.",
        )


def _new_email_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _create_support_email(payload: ContactSupportRequest) -> EmailContent:
    body_html = (
        "<p>A new support request was submitted from Project Atlas.</p>"
        f"<p><strong>Name:</strong> {escape(payload.name)}</p>"
        f"<p><strong>Email:</strong> {escape(payload.email)}</p>"
        f"<p><strong>Subject:</strong> {escape(payload.subject)}</p>"
        f"<p><strong>Message:</strong><br />{escape(payload.message).replace(chr(10), '<br />')}</p>"
    )
    return EmailContent(
        subject=f"Project Atlas support: {payload.subject}",
        html=body_html,
        text=(
            "New Project Atlas support request\n\n"
            f"Name: {payload.name}\n"
            f"Email: {payload.email}\n"
            f"Subject: {payload.subject}\n\n"
            f"{payload.message}"
        ),
    )


async def _issue_refresh_token(user_id: int) -> str:
    refresh_token = str(uuid4())
    await redis_client.setex(f"refresh:{refresh_token}", _refresh_token_ttl_seconds(), str(user_id))
    return refresh_token


async def _create_default_settings(db: AsyncSession, user_id: int) -> None:
    db.add(UserSettings(user_id=user_id))


async def _deliver_email_task(coro: Awaitable[None], *, context: str) -> None:
    try:
        await coro
    except Exception:
        logger.exception("Background email task failed for {}", context)


def _queue_email(coro: Awaitable[None], *, context: str) -> None:
    asyncio.create_task(_deliver_email_task(coro, context=context))


async def _send_verification_email(user: User) -> None:
    if not user.email_verification_token:
        return
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={user.email_verification_token}&email={user.email}"
    await mail_service.send(
        to_email=user.email,
        content=verification_email(full_name=user.full_name, verification_link=verification_link),
    )


async def _send_email_otp(user: User, otp_code: str) -> None:
    await mail_service.send(
        to_email=user.email,
        content=otp_email(full_name=user.full_name, otp_code=otp_code),
    )


async def _send_password_reset_email(user: User) -> None:
    if not user.password_reset_token:
        return
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={user.password_reset_token}"
    await mail_service.send(
        to_email=user.email,
        content=password_reset_email(full_name=user.full_name, reset_link=reset_link),
    )


async def _send_welcome_email(user: User) -> None:
    await mail_service.send(
        to_email=user.email,
        content=welcome_email(full_name=user.full_name, dashboard_link=f"{settings.FRONTEND_URL}/dashboard"),
    )


async def _mark_user_verified(db: AsyncSession, user: User) -> bool:
    if user.is_email_verified:
        return False
    user.is_email_verified = True
    user.email_verification_token = None
    user.email_otp_code_hash = None
    user.email_otp_expires = None
    user.email_otp_sent_at = None
    await db.commit()
    return True


async def _maybe_send_welcome_email(user: User, *, newly_verified: bool, context: str) -> None:
    if newly_verified:
        _queue_email(_send_welcome_email(user), context=context)


async def _bootstrap_social_user(
    *,
    db: AsyncSession,
    email: str,
    full_name: str | None,
    github_username: str | None = None,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            github_username=github_username,
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()
        await _create_default_settings(db, user.id)
        await db.commit()
        await db.refresh(user)
        _queue_email(_send_welcome_email(user), context=f"social-welcome:{user.id}")
        return user

    user.github_username = github_username or user.github_username
    if full_name and not user.full_name:
        user.full_name = full_name
    user.is_email_verified = True
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    _require_email_service()

    result = await db.execute(select(User).where(User.email == payload.email))
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        email_verification_token=str(uuid4()),
    )

    db.add(user)
    await db.flush()
    await _create_default_settings(db, user.id)
    await db.commit()
    await db.refresh(user)
    _queue_email(_send_verification_email(user), context=f"register-verification:{user.id}")
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    email = form_data.username.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Request a new verification link or OTP to continue.",
        )
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
        domain=settings.COOKIE_DOMAIN,
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

    newly_verified = await _mark_user_verified(db, user)
    await _maybe_send_welcome_email(user, newly_verified=newly_verified, context=f"welcome-token:{user.id}")
    return {"status": "verified"}


@router.post("/request-email-otp")
@limiter.limit("3/minute")
async def request_email_otp(
    request: Request,
    payload: EmailOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    _require_email_service()

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or user.is_email_verified:
        return {"status": "otp_sent"}

    otp_code = _new_email_otp()
    user.email_otp_code_hash = hash_password(otp_code)
    user.email_otp_expires = datetime.now(UTC) + timedelta(minutes=EMAIL_OTP_TTL_MINUTES)
    user.email_otp_sent_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    _queue_email(_send_email_otp(user, otp_code), context=f"verification-otp:{user.id}")
    return {"status": "otp_sent"}


@router.post("/verify-email-otp")
@limiter.limit("5/minute")
async def verify_email_otp(
    request: Request,
    payload: VerifyEmailOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not user.email_otp_code_hash or not user.email_otp_expires:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code.")

    if user.email_otp_expires <= datetime.now(UTC):
        user.email_otp_code_hash = None
        user.email_otp_expires = None
        user.email_otp_sent_at = None
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code.")

    if not verify_password(payload.otp, user.email_otp_code_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code.")

    newly_verified = await _mark_user_verified(db, user)
    await _maybe_send_welcome_email(user, newly_verified=newly_verified, context=f"welcome-otp:{user.id}")
    return {"status": "verified"}


@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    _require_email_service()

    result = await db.execute(select(User).where(User.email == payload.email))
    current_user = result.scalar_one_or_none()
    if current_user is None:
        return {"status": "verification_resent"}
    if current_user.is_email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already verified.")

    current_user.email_verification_token = str(uuid4())
    await db.commit()
    await db.refresh(current_user)
    _queue_email(_send_verification_email(current_user), context=f"resend-verification:{current_user.id}")
    return {"status": "verification_resent"}


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    _require_email_service()

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is not None:
        user.password_reset_token = str(uuid4())
        user.password_reset_expires = datetime.now(UTC) + timedelta(hours=1)
        await db.commit()
        await db.refresh(user)
        _queue_email(_send_password_reset_email(user), context=f"password-reset:{user.id}")
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


@router.post("/contact-support")
@limiter.limit("2/minute")
async def contact_support(
    request: Request,
    payload: ContactSupportRequest,
) -> dict[str, str]:
    _require_email_service()

    await mail_service.send(
        to_email=settings.SYSTEM_FROM_EMAIL,
        content=_create_support_email(payload),
        reply_to=payload.email,
    )
    return {"status": "sent"}


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

    user = await _bootstrap_social_user(
        db=db,
        email=userinfo["email"].strip().lower(),
        full_name=userinfo.get("name"),
    )
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

    user = await _bootstrap_social_user(
        db=db,
        email=primary_email.strip().lower(),
        full_name=github_user.get("name"),
        github_username=github_user.get("login"),
    )
    github_username = github_user.get("login")
    if isinstance(github_username, str) and github_username.strip():
        user.github_username = github_username.strip()
        user.github_metadata = await scan_github_repos(
            username=user.github_username,
            access_token=github_tokens["access_token"],
        )
        await refresh_profile_completeness(db, user_id=user.id)
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(subject=str(user.id), email=user.email)
    refresh_token = await _issue_refresh_token(user.id)
    redirect = RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard/profile?github=connected&access_token={access_token}")
    _set_refresh_cookie(redirect, refresh_token, _refresh_token_ttl_seconds())
    return redirect
