from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    filename: str
    format: str
    label: str | None
    status: str
    is_primary: bool
    structural_score: float | None
    semantic_score: float | None
    ats_score: float | None
    created_at: datetime
    updated_at: datetime | None


class ResumeUpdate(BaseModel):
    label: str | None = None
    is_primary: bool | None = None

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class ResumeStatusRead(BaseModel):
    status: str
    structural_score: float | None
    semantic_score: float | None
    ats_score: float | None
