from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from app.services.scrapers.base import BaseJobAdapter, CrawlResult, JobItem
from app.services.scrapers.utils import (
    clean_text,
    crawl_limits_for_source,
    extract_candidate_job_links,
    extract_next_page_url,
    fetch_html_with_playwright,
    json_ld_job_postings,
    limit_jobs_for_source,
    map_json_ld_to_job_item,
    rate_limit_delay,
    unique_urls,
)


class WellfoundAdapter(BaseJobAdapter):
    source_name = "wellfound"
    domains = ["wellfound.com", "www.wellfound.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        await rate_limit_delay(self.source_name)
        html = await fetch_html_with_playwright(url)
        return limit_jobs_for_source(self.source_name, self.parse(html))

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
            pending_detail_urls.extend(extract_candidate_job_links(search_html, next_page_url))
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
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobItem] = []

        for item in json_ld_job_postings(html):
            job = map_json_ld_to_job_item(item)
            if job and self._is_india_relevant(job.location):
                jobs.append(job)

        if jobs:
            return jobs

        for card in soup.select('[data-test="JobListingCard"]'):
            title = card.select_one('[data-test="JobListingCard-title"]')
            company = card.select_one('[data-test="JobListingCard-company"]')
            location = card.select_one('[data-test="JobListingCard-location"]')
            link = card.select_one("a[href]")
            if not title or not company or not link:
                continue

            url = clean_text(link.get("href"))
            if url and not url.startswith("http"):
                url = f"https://wellfound.com{url}"
            location_text = clean_text(location.get_text(strip=True) if location else "")
            if not self._is_india_relevant(location_text) and "remote" not in location_text.lower():
                continue

            jobs.append(
                JobItem(
                    title=clean_text(title.get_text(strip=True)),
                    company=clean_text(company.get_text(strip=True)),
                    location=location_text or None,
                    description=card.get_text(" ", strip=True)[:2000],
                    work_type=["full_time"],
                    source_url=url,
                    posted_at=None,
                    salary_min=None,
                    salary_max=None,
                    experience_required=None,
                )
            )
        return jobs

    def _is_india_relevant(self, location: str | None) -> bool:
        text = clean_text(location).lower()
        if not text:
            return False
        india_keywords = [
            "india",
            "bangalore",
            "bengaluru",
            "mumbai",
            "delhi",
            "hyderabad",
            "pune",
            "chennai",
            "kolkata",
            "remote",
            "anywhere",
        ]
        return any(keyword in text for keyword in india_keywords)
