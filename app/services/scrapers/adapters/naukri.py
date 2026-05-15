from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from app.services.scrapers.base import BaseJobAdapter, CrawlResult, JobItem
from app.services.scrapers.utils import (
    absolutize_url,
    clean_text,
    crawl_limits_for_source,
    extract_next_page_url,
    extract_experience_required,
    extract_location,
    fetch_html_with_playwright,
    json_ld_job_postings,
    limit_jobs_for_source,
    map_json_ld_to_job_item,
    rate_limit_delay,
    unique_urls,
)


class NaukriAdapter(BaseJobAdapter):
    source_name = "naukri"
    domains = ["naukri.com", "www.naukri.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        await rate_limit_delay(self.source_name)
        html = await fetch_html_with_playwright(url)
        jobs = self.parse(html)
        if not jobs:
            jobs = self._parse_search_results(html, base_url=url)
        return limit_jobs_for_source(self.source_name, jobs)

    async def crawl_jobs(
        self,
        url: str,
        keywords: list[str] | None = None,
        cursor: dict[str, Any] | None = None,
    ) -> CrawlResult:
        del keywords
        limits = crawl_limits_for_source(self.source_name)
        next_page_url = clean_text((cursor or {}).get("next_page_url")) or url
        pending_detail_urls = unique_urls(list((cursor or {}).get("pending_detail_urls") or []))
        jobs: list[JobItem] = []
        pages_scanned = 0
        detail_pages_scanned = 0

        while pending_detail_urls and detail_pages_scanned < limits["max_detail_pages_per_run"] and len(jobs) < limits["max_jobs_per_run"]:
            detail_url = pending_detail_urls.pop(0)
            await rate_limit_delay(self.source_name)
            detail_html = await fetch_html_with_playwright(detail_url)
            detail_jobs = self.parse(detail_html)
            if detail_jobs:
                jobs.append(detail_jobs[0])
            detail_pages_scanned += 1

        while next_page_url and pages_scanned < limits["max_pages_per_run"] and len(jobs) < limits["max_jobs_per_run"]:
            await rate_limit_delay(self.source_name)
            search_html = await fetch_html_with_playwright(next_page_url)
            pending_detail_urls.extend(self._extract_listing_urls(search_html, next_page_url))
            pending_detail_urls = unique_urls(pending_detail_urls)
            pages_scanned += 1
            next_page_url = extract_next_page_url(search_html, next_page_url)

            while pending_detail_urls and detail_pages_scanned < limits["max_detail_pages_per_run"] and len(jobs) < limits["max_jobs_per_run"]:
                detail_url = pending_detail_urls.pop(0)
                await rate_limit_delay(self.source_name)
                detail_html = await fetch_html_with_playwright(detail_url)
                detail_jobs = self.parse(detail_html)
                if detail_jobs:
                    jobs.append(detail_jobs[0])
                detail_pages_scanned += 1

        if not next_page_url and not pending_detail_urls:
            next_page_url = url

        return CrawlResult(
            jobs=limit_jobs_for_source(self.source_name, jobs),
            next_page_url=next_page_url,
            pending_detail_urls=pending_detail_urls[: limits["max_jobs_per_run"]],
            pages_scanned=pages_scanned,
            detail_pages_scanned=detail_pages_scanned,
        )

    def parse(self, html: str) -> list[JobItem]:
        jobs: list[JobItem] = []
        for item in json_ld_job_postings(html):
            job = self._parse_json_ld_job(item)
            if job is not None:
                jobs.append(job)
        return jobs

    def _parse_json_ld_job(self, item: dict) -> JobItem | None:
        job = map_json_ld_to_job_item(item)
        if job is None:
            return None

        salary_min = self._salary_bound(item.get("baseSalary", {}), prefer="minValue")
        salary_max = self._salary_bound(item.get("baseSalary", {}), prefer="maxValue")
        if salary_min is not None:
            job.salary_min = salary_min
        if salary_max is not None:
            job.salary_max = salary_max
        job.location = extract_location(item.get("jobLocation"))
        job.work_type = self._normalise_employment_type(item.get("employmentType"))
        job.experience_required = extract_experience_required(item)
        job.description = BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ", strip=True)[:5000]
        return job

    def _parse_search_results(self, html: str, *, base_url: str) -> list[JobItem]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobItem] = []
        seen_urls: set[str] = set()
        for anchor in soup.select("a[href*='job-listings'], a[href*='/job-listings/']"):
            href = clean_text(anchor.get("href"))
            if not href:
                continue
            source_url = absolutize_url(href, base_url)
            if source_url in seen_urls:
                continue
            seen_urls.add(source_url)
            title = clean_text(anchor.get_text(" ", strip=True))
            if not title:
                continue
            jobs.append(
                JobItem(
                    title=title,
                    company=clean_text(anchor.get("data-company")) or "Unknown company",
                    location=clean_text(anchor.get("data-location")) or None,
                    description=title,
                    work_type=["full_time"],
                    source_url=source_url,
                    posted_at=None,
                    salary_min=None,
                    salary_max=None,
                    experience_required=None,
                )
            )
        return jobs

    def _extract_listing_urls(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for anchor in soup.select("a[href*='job-listings'], a[href*='/job-listings/']"):
            href = clean_text(anchor.get("href"))
            if href:
                urls.append(absolutize_url(href, base_url))
        return unique_urls(urls)

    def _normalise_employment_type(self, raw: object) -> list[str]:
        values = raw if isinstance(raw, list) else [raw]
        mapping = {
            "FULL_TIME": "full_time",
            "Full-time": "full_time",
            "Permanent": "full_time",
            "PART_TIME": "part_time",
            "Part-time": "part_time",
            "CONTRACTOR": "contract",
            "Contract": "contract",
            "Freelance": "freelance",
            "INTERN": "internship",
            "Internship": "internship",
        }
        normalized: list[str] = []
        for value in values:
            key = clean_text(str(value))
            if not key:
                continue
            mapped = mapping.get(key)
            if mapped and mapped not in normalized:
                normalized.append(mapped)
        return normalized or ["full_time"]

    def _salary_bound(self, base_salary: dict, *, prefer: str) -> int | None:
        if not isinstance(base_salary, dict):
            return None
        value = base_salary.get("value", {})
        if isinstance(value, dict):
            raw = value.get(prefer) or value.get("value")
        else:
            raw = value
        try:
            return int(float(raw)) if raw is not None else None
        except (TypeError, ValueError):
            return None
