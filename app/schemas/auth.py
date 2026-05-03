from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    is_superuser: bool
    is_email_verified: bool
    full_name: str | None
    phone: str | None
    location: str | None
    bio: str | None
    linkedin_url: str | None
    github_username: str | None
    portfolio_url: str | None
    experience_level: str | None
    target_work_types: list[str] | None
    target_roles: list[str] | None
    target_locations: list[str] | None
    skills: list[str] | None
    github_metadata: dict | list | None
    has_completed_onboarding: bool
    profile_completeness: int
    created_at: datetime
    updated_at: datetime | None


class Token(BaseModel):
    access_token: str
    token_type: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
