from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProfileCompletenessMissingField(BaseModel):
    field: str
    points: int
    action_url: str


class ProfileCompletenessRead(BaseModel):
    score: int
    missing: list[ProfileCompletenessMissingField]


class GitHubScanMetadata(BaseModel):
    languages: dict[str, int]
    topics: list[str]
    top_repos: list[dict[str, str | int | None]]
    total_stars: int


class GitHubScanRead(BaseModel):
    status: str
    github_username: str | None = None
    metadata: GitHubScanMetadata | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    bio: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    experience_level: Literal["fresher", "junior", "mid", "senior", "lead"] | None = None
    target_work_types: list[str] | None = None
    target_roles: list[str] | None = Field(default=None, max_length=10)
    target_locations: list[str] | None = None
    skills: list[str] | None = None

    @field_validator(
        "full_name",
        "phone",
        "location",
        "bio",
        "linkedin_url",
        "portfolio_url",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("target_work_types", "target_roles", "target_locations", "skills", mode="before")
    @classmethod
    def normalize_optional_string_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized_values = [item.strip() for item in value if item and item.strip()]
        return normalized_values or None

    @field_validator("target_work_types")
    @classmethod
    def validate_target_work_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None

        allowed_values = {"full_time", "part_time", "internship", "contract", "freelance"}
        invalid_values = [item for item in value if item not in allowed_values]
        if invalid_values:
            raise ValueError(
                "target_work_types must only contain: full_time, part_time, internship, contract, freelance."
            )
        return value

    @field_validator("target_roles")
    @classmethod
    def validate_target_roles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > 10:
            raise ValueError("target_roles cannot contain more than 10 entries.")
        return value

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.lower() for item in value]
