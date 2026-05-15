from __future__ import annotations

from bs4 import BeautifulSoup

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, fetch_html_with_playwright, limit_jobs_for_source, rate_limit_delay


class HiristAdapter(BaseJobAdapter):
    source_name = "hirist"
    domains = ["hirist.com", "www.hirist.com", "hirist.tech", "www.hirist.tech"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        await rate_limit_delay(self.source_name)
        html = await fetch_html_with_playwright(url)
        return limit_jobs_for_source(self.source_name, self.parse(html))

    def parse(self, html: str) -> list[JobItem]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobItem] = []
        for card in soup.select(".job-list-item, .job-item, article"):
            title_el = card.select_one("h2 a, .job-title a, h3 a")
            company_el = card.select_one(".company-name, .job-company-name")
            location_el = card.select_one(".job-location, .location-text")
            exp_el = card.select_one(".experience, .exp-text")
            if not title_el or not company_el:
                continue
            url = clean_text(title_el.get("href"))
            if url and not url.startswith("http"):
                url = f"https://www.hirist.tech{url}"
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
                    experience_required=clean_text(exp_el.get_text(strip=True) if exp_el else "") or None,
                )
            )
        return jobs
