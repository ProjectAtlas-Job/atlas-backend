from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from app.services.scrapers.base import BaseJobAdapter, CrawlResult, JobItem
from app.services.scrapers.utils import (
    clean_text,
    crawl_limits_for_source,
    extract_next_page_url,
    fetch_html_with_playwright,
    limit_jobs_for_source,
    parse_compensation_text,
    rate_limit_delay,
)


class InternshalaAdapter(BaseJobAdapter):
    source_name = "internshala"
    domains = ["internshala.com", "www.internshala.com"]

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
        jobs: list[JobItem] = []
        pages_scanned = 0

        while next_page_url and pages_scanned < limits["max_pages_per_run"] and len(jobs) < limits["max_jobs_per_run"]:
            await rate_limit_delay(self.source_name)
            html = await fetch_html_with_playwright(next_page_url)
            jobs.extend(self.parse(html))
            pages_scanned += 1
            next_page_url = extract_next_page_url(html, next_page_url)

        if not next_page_url:
            next_page_url = url

        return CrawlResult(
            jobs=limit_jobs_for_source(self.source_name, jobs),
            next_page_url=next_page_url,
            pending_detail_urls=[],
            pages_scanned=pages_scanned,
            detail_pages_scanned=0,
        )

    def parse(self, html: str) -> list[JobItem]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobItem] = []
        containers = soup.select(".individual_internship") or soup.select(".internship_meta")

        for container in containers:
            title_el = container.select_one(".profile a") or container.select_one("h3 a") or container.select_one(".job-title-href")
            company_el = container.select_one(".company_name a") or container.select_one(".company_name") or container.select_one(".company-name")
            location_el = container.select_one(".location_link") or container.select_one(".location span")
            stipend_el = container.select_one(".stipend") or container.select_one(".salary")
            duration_el = container.select_one(".other_detail_item span")
            link_el = title_el or container.select_one("a[href]")

            title = clean_text(title_el.get_text(strip=True) if title_el else "")
            company = clean_text(company_el.get_text(strip=True) if company_el else "")
            if not title or not company:
                continue

            source_url = clean_text(link_el.get("href") if link_el else "")
            if source_url and not source_url.startswith("http"):
                source_url = f"https://internshala.com{source_url}"

            stipend_text = clean_text(stipend_el.get_text(strip=True) if stipend_el else "")
            salary_min, salary_max = parse_compensation_text(stipend_text, annualize_monthly=True)

            jobs.append(
                JobItem(
                    title=title,
                    company=company,
                    location=clean_text(location_el.get_text(strip=True) if location_el else "") or "Remote",
                    description=container.get_text(" ", strip=True)[:2000],
                    work_type=["internship"],
                    source_url=source_url,
                    posted_at=None,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    experience_required=clean_text(duration_el.get_text(strip=True) if duration_el else "") or None,
                )
            )
        return jobs
