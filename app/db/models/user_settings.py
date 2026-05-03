from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base_class import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    llm_provider: Mapped[str] = mapped_column(String, nullable=False, server_default="gemini")
    llm_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_model: Mapped[str] = mapped_column(
        String, nullable=False, server_default="gemini-2.0-flash"
    )
    use_platform_api_key: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    smtp_server: Mapped[str | None] = mapped_column(String, nullable=True)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, server_default="587")
    smtp_username: Mapped[str | None] = mapped_column(String, nullable=True)
    smtp_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_gmail_for_send: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_inbox_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_apply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    auto_apply_daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    auto_submit_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    cold_mail_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    cold_mail_daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    match_threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.65")
    scrape_urls: Mapped[list[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, server_default="[]"
    )
    follow_up_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="settings")
