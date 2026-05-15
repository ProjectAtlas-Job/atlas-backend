from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobPostingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int | None
    company_name_raw: str
    title: str
    description: str
    location: str | None
    work_type: list[str]
    salary_min: int | None
    salary_max: int | None
    experience_required: str | None
    skills_required: list[str]
    source: str
    source_url: str
    is_active: bool
    posted_at: datetime | None
    scraped_at: datetime

    @field_validator("work_type", "skills_required", mode="before")
    @classmethod
    def normalize_array_fields(cls, value: list[str] | None) -> list[str]:
        return list(value or [])


class JobListRead(BaseModel):
    total: int
    items: list[JobPostingRead]
    skip: int
    limit: int


class JobMatchRead(BaseModel):
    job: JobPostingRead
    match_score: float


class JobMatchListRead(BaseModel):
    items: list[JobMatchRead]
    cached: bool
    generated_at: datetime


class UserJobSaveCreate(BaseModel):
    status: Literal["saved", "dismissed"]
    notes: str | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class UserJobSaveUpdate(BaseModel):
    status: Literal["saved", "dismissed", "applied"]
    notes: str | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class UserJobSaveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    job_id: int
    status: str
    match_score: float | None
    notes: str | None
    created_at: datetime


class SavedJobItemRead(BaseModel):
    save: UserJobSaveRead
    job: JobPostingRead


class SavedJobListRead(BaseModel):
    items: list[SavedJobItemRead]


class JobListParams(BaseModel):
    source: str | None = None
    work_type: str | None = None
    location: str | None = None
    posted_after: date | None = None
    search: str | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("source", "work_type", "location", "search", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None
