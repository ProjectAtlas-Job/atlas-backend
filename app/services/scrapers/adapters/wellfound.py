from __future__ import annotations

from playwright.async_api import async_playwright

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, json_ld_job_postings, map_json_ld_to_job_item


class WellfoundAdapter(BaseJobAdapter):
    source_name = "wellfound"
    domains = ["wellfound.com", "www.wellfound.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        html = await self._fetch_page_content(url)
        return self.parse(html)

    def parse(self, html: str) -> list[JobItem]:
        jobs: list[JobItem] = []
        for item in json_ld_job_postings(html):
            job = map_json_ld_to_job_item(item)
            if job is None:
                continue
            if self._is_india_friendly(job.location):
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

    def _is_india_friendly(self, location: str | None) -> bool:
        text = clean_text(location).lower()
        if not text:
            return True
        return "india" in text or any(
            city in text
            for city in ("bengaluru", "bangalore", "mumbai", "pune", "hyderabad", "chennai", "gurgaon", "gurugram", "delhi", "noida", "kolkata", "ahmedabad", "surat", "jaipur")
        )
