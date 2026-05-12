from pydantic import BaseModel, field_validator


class ProfileCompletenessMissingField(BaseModel):
    field: str
    points: int
    action_url: str


class ProfileCompletenessRead(BaseModel):
    score: int
    missing: list[ProfileCompletenessMissingField]


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    bio: str | None = None
    linkedin_url: str | None = None
    github_username: str | None = None
    portfolio_url: str | None = None
    experience_level: str | None = None
    target_work_types: list[str] | None = None
    target_roles: list[str] | None = None
    target_locations: list[str] | None = None
    skills: list[str] | None = None
    has_completed_onboarding: bool | None = None

    @field_validator(
        "full_name",
        "phone",
        "location",
        "bio",
        "linkedin_url",
        "github_username",
        "portfolio_url",
        "experience_level",
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
