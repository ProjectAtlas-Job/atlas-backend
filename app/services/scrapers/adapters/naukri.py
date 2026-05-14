from __future__ import annotations

from urllib.parse import urlparse

from playwright.async_api import async_playwright

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import absolutize_url, clean_text, json_ld_job_postings, map_json_ld_to_job_item, normalise_work_types


class NaukriAdapter(BaseJobAdapter):
    source_name = "naukri"
    domains = ["naukri.com", "www.naukri.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        html = await self._fetch_page_content(url)
        if self._is_listing_url(url):
            return self.parse(html)
        return self._parse_search_results(html, base_url=url)

    def parse(self, html: str) -> list[JobItem]:
        jobs: list[JobItem] = []
        for item in json_ld_job_postings(html):
            job = map_json_ld_to_job_item(item)
            if job is None:
                continue
            job.work_type = normalise_work_types(item.get("employmentType"))
            jobs.append(job)
        return jobs

    async def _fetch_page_content(self, url: str) -> str:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                return await page.content()
            finally:
                await browser.close()

    def _parse_search_results(self, html: str, *, base_url: str) -> list[JobItem]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobItem] = []
        seen_urls: set[str] = set()
        for anchor in soup.select("a[href*='job-listings'], a[href*='/job-listings/']"):
            href = anchor.get("href")
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
                    work_type=[],
                    source_url=source_url,
                    posted_at=None,
                    salary_min=None,
                    salary_max=None,
                )
            )
        return jobs

    def _is_listing_url(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return "job-listings" in path or path.count("/") > 2
