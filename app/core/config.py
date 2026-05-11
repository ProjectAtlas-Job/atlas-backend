from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/atlas"
    SECRET_KEY: str = "change-me"
    FERNET_KEY: str = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    REDIS_URL: str = "redis://localhost:6379/0"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    FRONTEND_URL: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    # Gmail SMTP uses STARTTLS on port 587, so secure remains false until the
    # server upgrades the connection. Google requires 2FA to be enabled and a
    # dedicated App Password for SMTP access. Do not use a regular Gmail password.
    SMTP_HOST: str = Field(default="", validation_alias="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, validation_alias="SMTP_PORT")
    SMTP_USER: str = Field(default="", validation_alias="SMTP_USER")
    SMTP_PASS: str = Field(default="", validation_alias="SMTP_PASS")
    SMTP_FROM: str = Field(default="", validation_alias="SMTP_FROM")
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/github/callback"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                return [item.strip().strip("\"'") for item in stripped[1:-1].split(",") if item.strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        raise ValueError("BACKEND_CORS_ORIGINS must be a list or comma-separated string.")

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.lower()
        allowed = {"development", "staging", "production", "test"}
        if normalized not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("BACKEND_CORS_ORIGINS")
    @classmethod
    def validate_production_cors(cls, value: list[str], info: Any) -> list[str]:
        environment = info.data.get("ENVIRONMENT", "development")
        if environment == "production" and "*" in value:
            raise ValueError("Wildcard CORS origins are not allowed in production.")
        return value

    @model_validator(mode="after")
    def validate_smtp_settings(self) -> "Settings":
        smtp_values = [self.SMTP_HOST, self.SMTP_USER, self.SMTP_PASS, self.SMTP_FROM]
        populated = [bool(value.strip()) for value in smtp_values]
        if any(populated) and not all(populated):
            raise ValueError("SMTP_HOST, SMTP_USER, SMTP_PASS, and SMTP_FROM must be provided together.")
        return self

    @property
    def email_enabled(self) -> bool:
        return all(
            value.strip()
            for value in (
                self.SMTP_HOST,
                self.SMTP_USER,
                self.SMTP_PASS,
                self.SMTP_FROM,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
