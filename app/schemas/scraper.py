from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl, field_validator


class ManualJobSubmissionRequest(BaseModel):
    url: HttpUrl

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: str | HttpUrl) -> str | HttpUrl:
        if isinstance(value, str):
            return value.strip()
        return value


class ManualJobSubmissionQueuedResponse(BaseModel):
    status: Literal["queued"]
    message: str


class ManualJobSubmissionDuplicateResponse(BaseModel):
    status: Literal["already_exists"]
    job_id: int


class ScraperRunRequest(BaseModel):
    url: HttpUrl
    target_type: Literal["jobs", "contacts"]
    keywords: list[str] | None = None

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: str | HttpUrl) -> str | HttpUrl:
        if isinstance(value, str):
            return value.strip()
        return value


class ScraperRunResponse(BaseModel):
    task_id: str


class ScraperStopResponse(BaseModel):
    cancelled: int


class ScraperStatusItem(BaseModel):
    task_id: str
    url: str | None
    started_at: datetime
    status: str
