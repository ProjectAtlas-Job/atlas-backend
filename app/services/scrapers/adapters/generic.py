from __future__ import annotations

import re
from typing import Any

import httpx
from pydantic import BaseModel

from app.services.llm import call_llm
from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, html_to_visible_text, json_ld_job_postings, map_json_ld_to_job_item


class JobItemExtraction(BaseModel):
    title: str
    company: str
    location: str | None = None
    description: str
    work_type: list[str] = []
    source_url: str
    posted_at: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None


class JobListExtraction(BaseModel):
    jobs: list[JobItemExtraction]


class GenericAdapter(BaseJobAdapter):
    source_name = "scraper"
    domains: list[str] = []

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        return self.parse(response.text, url=url)

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
                    work_type=list(job.work_type),
                    source_url=source_url,
                    posted_at=clean_text(job.posted_at) or None,
                    salary_min=job.salary_min,
                    salary_max=job.salary_max,
                )
            )
        return parsed_jobs


def _heuristic_extract_jobs(text: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    for index, line in enumerate(lines):
        if not re.search(r"\b(job|role|hiring|position|opening)\b", line, re.IGNORECASE):
            continue
        company = "Unknown company"
        title = line
        if ":" in line:
            company_part, _, title_part = line.partition(":")
            company = clean_text(company_part)
            title = clean_text(title_part) or line
        description = " ".join(lines[index : index + 3])
        jobs.append(
            {
                "title": title,
                "company": company,
                "location": None,
                "description": description,
                "work_type": [],
                "source_url": "",
                "posted_at": None,
                "salary_min": None,
                "salary_max": None,
            }
        )
        if len(jobs) >= 5:
            break
    return jobs


__all__ = ["GenericAdapter", "JobListExtraction", "_heuristic_extract_jobs"]
