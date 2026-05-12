from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text, event, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email_verification_token: Mapped[str | None] = mapped_column(String, nullable=True)
    email_otp_code_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    email_otp_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_otp_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_token: Mapped[str | None] = mapped_column(String, nullable=True)
    password_reset_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    github_username: Mapped[str | None] = mapped_column(String, nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String, nullable=True)
    target_work_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    target_roles: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    target_locations: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    github_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    profile_completeness: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    settings: Mapped["UserSettings | None"] = relationship(
        "UserSettings", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    resumes: Mapped[list["Resume"]] = relationship("Resume", back_populates="user")


@event.listens_for(User, "before_insert")
def lowercase_user_email_before_insert(mapper, connection, target: User) -> None:  # type: ignore[no-untyped-def]
    if target.email:
        target.email = target.email.lower()


@event.listens_for(User, "before_update")
def lowercase_user_email_before_update(mapper, connection, target: User) -> None:  # type: ignore[no-untyped-def]
    if target.email:
        target.email = target.email.lower()
