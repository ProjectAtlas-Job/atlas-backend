from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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


@dataclass(slots=True)
class CrawlResult:
    jobs: list[JobItem]
    next_page_url: str | None = None
    pending_detail_urls: list[str] = field(default_factory=list)
    pages_scanned: int = 0
    detail_pages_scanned: int = 0


class BaseJobAdapter(ABC):
    source_name: str
    domains: list[str]

    @abstractmethod
    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        """Fetch page at url, parse, and return JobItems. Used by ARQ scraper task."""

    async def crawl_jobs(
        self,
        url: str,
        keywords: list[str] | None = None,
        cursor: dict[str, Any] | None = None,
    ) -> CrawlResult:
        del cursor
        jobs = await self.fetch_jobs(url, keywords=keywords)
        return CrawlResult(jobs=jobs, next_page_url=url, pages_scanned=1)

    @abstractmethod
    def parse(self, html: str) -> list[JobItem]:
        """Parse already-fetched HTML and return JobItems. Used by JobScraperAgent."""
