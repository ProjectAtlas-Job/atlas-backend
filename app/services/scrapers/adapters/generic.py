from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from app.services.llm import call_llm
from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, fetch_html_with_playwright, html_to_visible_text, json_ld_job_postings, limit_jobs_for_source, map_json_ld_to_job_item, normalise_work_types, rate_limit_delay


class JobItemExtraction(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Hiring company name")
    location: str | None = Field(default=None, description="City or region. Remote if remote.")
    description: str = Field(description="Full job description text")
    work_type: list[str] = Field(default_factory=list, description="Normalized work types")
    source_url: str = Field(description="Direct URL to this job listing")
    posted_at: str | None = Field(default=None, description="ISO date string if visible, else null")
    salary_min: int | None = Field(default=None, description="Minimum annual salary in INR if visible")
    salary_max: int | None = Field(default=None, description="Maximum annual salary in INR if visible")
    experience_required: str | None = Field(default=None, description="Experience requirement if visible")


class JobListExtraction(BaseModel):
    jobs: list[JobItemExtraction]


class GenericAdapter(BaseJobAdapter):
    source_name = "scraper"
    domains: list[str] = []

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        await rate_limit_delay(self.source_name)
        html = await self._fetch_html(url)
        return limit_jobs_for_source(self.source_name, self.parse(html, url=url))

    def parse(self, html: str, url: str = "") -> list[JobItem]:
        jobs = [job for item in json_ld_job_postings(html) if (job := map_json_ld_to_job_item(item, default_url=url)) is not None]
        if jobs:
            return jobs

        page_text = html_to_visible_text(html)[:15000]
        extraction = call_llm(page_text, response_model=JobListExtraction)
        parsed_jobs: list[JobItem] = []
        for job in extraction.jobs:
            source_url = clean_text(job.source_url) or url
            if not source_url:
                continue
            parsed_jobs.append(
                JobItem(
                    title=clean_text(job.title) or "Untitled role",
                    company=clean_text(job.company) or "Unknown company",
                    location=clean_text(job.location) or None,
                    description=clean_text(job.description) or clean_text(job.title),
                    work_type=normalise_work_types(job.work_type),
                    source_url=source_url,
                    posted_at=clean_text(job.posted_at) or None,
                    salary_min=job.salary_min,
                    salary_max=job.salary_max,
                    experience_required=clean_text(job.experience_required) or None,
                )
            )
        return parsed_jobs

    async def _fetch_html(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception:
            return await fetch_html_with_playwright(url)


def _heuristic_extract_jobs(text: str) -> list[dict[str, object]]:
    jobs: list[dict[str, object]] = []
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    for index, line in enumerate(lines):
        if "job" not in line.lower() and "hiring" not in line.lower() and "role" not in line.lower():
            continue
        company = "Unknown company"
        title = line
        if ":" in line:
            company_part, _, title_part = line.partition(":")
            company = clean_text(company_part)
            title = clean_text(title_part) or line
        jobs.append(
            {
                "title": title,
                "company": company,
                "location": None,
                "description": " ".join(lines[index : index + 3]),
                "work_type": [],
                "source_url": "",
                "posted_at": None,
                "salary_min": None,
                "salary_max": None,
                "experience_required": None,
            }
        )
        if len(jobs) >= 5:
            break
    return jobs


__all__ = ["GenericAdapter", "JobListExtraction", "_heuristic_extract_jobs"]
