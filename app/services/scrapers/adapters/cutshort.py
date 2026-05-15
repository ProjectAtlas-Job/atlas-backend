from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from app.services.scrapers.base import BaseJobAdapter, CrawlResult, JobItem
from app.services.scrapers.utils import (
    absolutize_url,
    clean_text,
    crawl_limits_for_source,
    extract_candidate_job_links,
    extract_next_page_url,
    fetch_html_with_playwright,
    json_ld_job_postings,
    limit_jobs_for_source,
    map_json_ld_to_job_item,
    normalise_work_types,
    parse_compensation_text,
    rate_limit_delay,
    unique_urls,
)


class CutshortAdapter(BaseJobAdapter):
    source_name = "cutshort"
    domains = ["cutshort.io", "www.cutshort.io"]

    GRAPHQL_URL = "https://cutshort.io/api/graphql"
    JOBS_QUERY = """
    query SearchJobs($page: Int) {
      jobs(page: $page) {
        data {
          id
          title
          description
          minSalary
          maxSalary
          minExp
          maxExp
          jobType
          url
          createdAt
          company { name }
          location { name }
        }
      }
    }
    """

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        crawl_result = await self.crawl_jobs(url, keywords=keywords)
        return crawl_result.jobs

    async def crawl_jobs(
        self,
        url: str,
        keywords: list[str] | None = None,
        cursor: dict[str, Any] | None = None,
    ) -> CrawlResult:
        api_jobs = await self._fetch_jobs_from_graphql()
        if api_jobs:
            return CrawlResult(jobs=limit_jobs_for_source(self.source_name, api_jobs), next_page_url=url, pages_scanned=1)

        del keywords
        limits = crawl_limits_for_source(self.source_name)
        next_page_url = clean_text((cursor or {}).get("next_page_url")) or url
        pending_urls = unique_urls(list((cursor or {}).get("pending_detail_urls") or []))
        jobs: list[JobItem] = []
        pages_scanned = 0
        detail_pages_scanned = 0

        while pending_urls and detail_pages_scanned < limits["max_detail_pages_per_run"] and len(jobs) < limits["max_jobs_per_run"]:
            detail_url = pending_urls.pop(0)
            detail_job = await self._fetch_detail_job(detail_url)
            detail_pages_scanned += 1
            if detail_job is not None:
                jobs.append(detail_job)

        while next_page_url and pages_scanned < limits["max_pages_per_run"] and len(jobs) < limits["max_jobs_per_run"]:
            await rate_limit_delay(self.source_name)
            page_html = await self._fetch_html(next_page_url)
            page_jobs = self._parse_listing_page(page_html, next_page_url)
            jobs.extend(page_jobs)
            pending_urls.extend(extract_candidate_job_links(page_html, next_page_url))
            pending_urls = unique_urls(
                [
                    candidate_url
                    for candidate_url in pending_urls
                    if candidate_url not in {job.source_url for job in jobs}
                ]
            )
            pages_scanned += 1
            next_page_url = extract_next_page_url(page_html, next_page_url)

            while pending_urls and detail_pages_scanned < limits["max_detail_pages_per_run"] and len(jobs) < limits["max_jobs_per_run"]:
                detail_url = pending_urls.pop(0)
                detail_job = await self._fetch_detail_job(detail_url)
                detail_pages_scanned += 1
                if detail_job is not None:
                    jobs.append(detail_job)

        deduped_jobs: list[JobItem] = []
        seen_urls: set[str] = set()
        for job in jobs:
            source_url = clean_text(job.source_url)
            if not source_url or source_url in seen_urls:
                continue
            seen_urls.add(source_url)
            job.source_url = absolutize_url(source_url, url)
            deduped_jobs.append(job)

        if not next_page_url and not pending_urls:
            next_page_url = url

        return CrawlResult(
            jobs=limit_jobs_for_source(self.source_name, deduped_jobs),
            next_page_url=next_page_url,
            pending_detail_urls=pending_urls[: limits["max_jobs_per_run"]],
            pages_scanned=pages_scanned,
            detail_pages_scanned=detail_pages_scanned,
        )

    def parse(self, html: str) -> list[JobItem]:
        return self._parse_page_jobs(html, base_url="https://cutshort.io/jobs")

    async def _fetch_jobs_from_graphql(self) -> list[JobItem]:
        await rate_limit_delay(self.source_name)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.GRAPHQL_URL,
                    json={"query": self.JOBS_QUERY, "variables": {"page": 1}},
                    headers={"Content-Type": "application/json", "Origin": "https://cutshort.io"},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        data = response.json()
        jobs = data.get("data", {}).get("jobs", {}).get("data", [])
        parsed_jobs = [
            JobItem(
                title=clean_text(job.get("title")),
                company=clean_text(job.get("company", {}).get("name")) or "Unknown company",
                location=clean_text(job.get("location", {}).get("name")) or "India",
                description=clean_text(job.get("description"))[:3000] or clean_text(job.get("title")),
                work_type=normalise_work_types(job.get("jobType")) or ["full_time"],
                source_url=clean_text(job.get("url")) or f"https://cutshort.io/job/{job.get('id', '')}",
                posted_at=clean_text(job.get("createdAt")) or None,
                salary_min=_safe_int(job.get("minSalary")),
                salary_max=_safe_int(job.get("maxSalary")),
                experience_required=self._experience_range(job.get("minExp"), job.get("maxExp")),
            )
            for job in jobs
            if clean_text(job.get("title"))
        ]
        return limit_jobs_for_source(self.source_name, parsed_jobs)

    async def _fetch_detail_job(self, detail_url: str) -> JobItem | None:
        await rate_limit_delay(self.source_name)
        detail_html = await self._fetch_html(detail_url)
        detail_jobs = self._parse_page_jobs(detail_html, base_url=detail_url)
        return detail_jobs[0] if detail_jobs else None

    async def _fetch_html(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception:
            return await fetch_html_with_playwright(url)

    def _parse_page_jobs(self, html: str, *, base_url: str) -> list[JobItem]:
        json_ld_jobs = [
            job
            for item in json_ld_job_postings(html)
            if (job := map_json_ld_to_job_item(item, default_url=base_url)) is not None
        ]
        if json_ld_jobs:
            return json_ld_jobs
        return self._parse_listing_page(html, base_url)

    def _parse_listing_page(self, html: str, base_url: str) -> list[JobItem]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobItem] = []
        seen_urls: set[str] = set()

        for card in soup.select("article, section, div"):
            job = self._build_card_job(card, base_url)
            if job is None or job.source_url in seen_urls:
                continue
            seen_urls.add(job.source_url)
            jobs.append(job)

        if jobs:
            return jobs

        return self._parse_anchor_fallback(soup, base_url)

    def _build_card_job(self, card: Tag, base_url: str) -> JobItem | None:
        link = card.select_one('a[href*="/job"]') or card.select_one('a[href*="/jobs"]')
        if not isinstance(link, Tag):
            return None

        source_url = absolutize_url(clean_text(link.get("href")), base_url)
        if "cutshort.io" not in source_url:
            return None

        title = self._select_text(card, ["h1", "h2", "h3", '[class*="title"]', '[data-testid*="title"]'])
        if not title:
            title = clean_text(link.get_text(" ", strip=True))
        if not title or len(title) < 3:
            return None

        company = self._select_text(card, ['[class*="company"]', '[data-testid*="company"]'])
        location = self._select_text(card, ['[class*="location"]', '[data-testid*="location"]']) or "India"
        compensation = self._select_text(card, ['[class*="salary"]', '[class*="compensation"]', '[class*="ctc"]'])
        salary_min, salary_max = parse_compensation_text(compensation)
        experience_required = self._select_text(card, ['[class*="experience"]', '[class*="exp"]'])
        description = clean_text(card.get_text(" ", strip=True))[:3000]

        if not company:
            company = self._infer_company_from_text(description)

        return JobItem(
            title=title,
            company=company or "Unknown company",
            location=location,
            description=description or title,
            work_type=["full_time"],
            source_url=source_url,
            posted_at=None,
            salary_min=salary_min,
            salary_max=salary_max,
            experience_required=experience_required or None,
        )

    def _parse_anchor_fallback(self, soup: BeautifulSoup, base_url: str) -> list[JobItem]:
        jobs: list[JobItem] = []
        for link in soup.select('a[href*="/job"], a[href*="/jobs"]'):
            href = clean_text(link.get("href"))
            title = clean_text(link.get_text(" ", strip=True))
            if not href or not title or len(title) < 3:
                continue
            source_url = absolutize_url(href, base_url)
            if "cutshort.io" not in source_url:
                continue
            surrounding = link.parent if isinstance(link.parent, Tag) else None
            description = clean_text(surrounding.get_text(" ", strip=True) if surrounding else title)[:3000]
            jobs.append(
                JobItem(
                    title=title,
                    company=self._infer_company_from_text(description) or "Unknown company",
                    location="India",
                    description=description or title,
                    work_type=["full_time"],
                    source_url=source_url,
                    posted_at=None,
                    salary_min=None,
                    salary_max=None,
                    experience_required=None,
                )
            )
        return limit_jobs_for_source(self.source_name, jobs)

    def _select_text(self, card: Tag, selectors: list[str]) -> str:
        for selector in selectors:
            element = card.select_one(selector)
            if isinstance(element, Tag):
                text = clean_text(element.get_text(" ", strip=True))
                if text:
                    return text
        return ""

    def _infer_company_from_text(self, text: str) -> str:
        cleaned = clean_text(text)
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        for separator in (" at ", " @ ", " | "):
            if separator in lowered:
                _, company_part = lowered.split(separator, 1)
                company_length = len(company_part)
                original_company = cleaned[-company_length:] if company_length else ""
                return clean_text(original_company.split(" - ", 1)[0])[:200]
        return ""

    def _experience_range(self, min_exp: object, max_exp: object) -> str | None:
        if min_exp is None and max_exp is None:
            return None
        if min_exp is None:
            return f"up to {max_exp} years"
        if max_exp is None:
            return f"{min_exp}+ years"
        return f"{min_exp}-{max_exp} years"


def _safe_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
