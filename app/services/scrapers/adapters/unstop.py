from __future__ import annotations

import httpx

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, limit_jobs_for_source, rate_limit_delay


class UnstopAdapter(BaseJobAdapter):
    source_name = "unstop"
    domains = ["unstop.com", "www.unstop.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del url, keywords
        await rate_limit_delay(self.source_name)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://unstop.com/api/public/opportunity/search-new",
                params={
                    "opportunity": "jobs",
                    "per_page": 50,
                    "page": 1,
                    "filters": '{"country":["India"]}',
                },
                headers={"Accept": "application/json", "Referer": "https://unstop.com"},
            )
            response.raise_for_status()
            data = response.json()

        opportunities = data.get("data", {}).get("data", [])
        jobs = [
            JobItem(
                title=clean_text(item.get("title")),
                company=clean_text(item.get("organisation", {}).get("name")),
                location=clean_text(item.get("city")) or "India",
                description=clean_text(item.get("description"))[:3000] or clean_text(item.get("title")),
                work_type=["full_time"],
                source_url=f"https://unstop.com/jobs/{item.get('id', '')}",
                posted_at=clean_text(item.get("start_date")) or None,
                salary_min=None,
                salary_max=None,
                experience_required=clean_text(item.get("eligibility")) or None,
            )
            for item in opportunities
            if clean_text(item.get("title"))
        ]
        return limit_jobs_for_source(self.source_name, jobs)

    def parse(self, html: str) -> list[JobItem]:
        del html
        return []
