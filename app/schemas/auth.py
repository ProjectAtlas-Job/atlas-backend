from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


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

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ResendVerificationRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class EmailOtpRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class VerifyEmailOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("otp", mode="before")
    @classmethod
    def normalize_otp(cls, value: str) -> str:
        return value.strip()


class ContactSupportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=180)
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("name", "subject", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("message", mode="before")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return value.strip()

    @field_validator("email", mode="before")
    @classmethod
    def normalize_support_email(cls, value: str) -> str:
        return value.strip().lower()
