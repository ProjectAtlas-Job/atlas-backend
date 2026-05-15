from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class JobItem:
    title: str
    company: str
    location: str | None
    description: str
    work_type: list[str]
    source_url: str
    posted_at: str | None
    salary_min: int | None
    salary_max: int | None
    experience_required: str | None = None


class BaseJobAdapter(ABC):
    source_name: str
    domains: list[str]

    @abstractmethod
    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        """Fetch page at url, parse, and return JobItems. Used by ARQ scraper task."""

    @abstractmethod
    def parse(self, html: str) -> list[JobItem]:
        """Parse already-fetched HTML and return JobItems. Used by JobScraperAgent."""
