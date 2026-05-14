from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.db.types import Vector


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    website: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    careers_page_url: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    industry: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    size_range: Mapped[str | None] = mapped_column(String, nullable=True)
    funding_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    hq_location: Mapped[str | None] = mapped_column(String, nullable=True)
    is_india_based: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tech_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[object | None] = mapped_column(Vector(384), nullable=True)
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
