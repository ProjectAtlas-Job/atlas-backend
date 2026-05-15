from __future__ import annotations

from bs4 import BeautifulSoup

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, fetch_html_with_playwright, limit_jobs_for_source, rate_limit_delay


class IIMJobsAdapter(BaseJobAdapter):
    source_name = "iimjobs"
    domains = ["iimjobs.com", "www.iimjobs.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        await rate_limit_delay(self.source_name)
        html = await fetch_html_with_playwright(url)
        return limit_jobs_for_source(self.source_name, self.parse(html))

    def parse(self, html: str) -> list[JobItem]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobItem] = []
        for card in soup.select(".job-container, .job-listing"):
            title_el = card.select_one(".job-title a, h2 a")
            company_el = card.select_one(".company-name, .job-company")
            location_el = card.select_one(".job-location, .location")
            link_el = title_el if title_el else card.select_one('a[href*="/jobs/"]')
            if not title_el or not company_el or link_el is None:
                continue
            url = clean_text(link_el.get("href"))
            if url and not url.startswith("http"):
                url = f"https://www.iimjobs.com{url}"
            jobs.append(
                JobItem(
                    title=clean_text(title_el.get_text(strip=True)),
                    company=clean_text(company_el.get_text(strip=True)),
                    location=clean_text(location_el.get_text(strip=True) if location_el else "") or "India",
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
