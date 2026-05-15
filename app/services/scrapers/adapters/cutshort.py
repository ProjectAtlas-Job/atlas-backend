from __future__ import annotations

import httpx

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, limit_jobs_for_source, rate_limit_delay


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
        del url, keywords
        await rate_limit_delay(self.source_name)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.GRAPHQL_URL,
                json={"query": self.JOBS_QUERY, "variables": {"page": 1}},
                headers={"Content-Type": "application/json", "Origin": "https://cutshort.io"},
            )
            response.raise_for_status()
            data = response.json()

        jobs = data.get("data", {}).get("jobs", {}).get("data", [])
        parsed_jobs = [
            JobItem(
                title=clean_text(job.get("title")),
                company=clean_text(job.get("company", {}).get("name")),
                location=clean_text(job.get("location", {}).get("name")) or "India",
                description=clean_text(job.get("description"))[:3000] or clean_text(job.get("title")),
                work_type=["full_time"],
                source_url=clean_text(job.get("url")) or f"https://cutshort.io/job/{job.get('id', '')}",
                posted_at=clean_text(job.get("createdAt")) or None,
                salary_min=job.get("minSalary"),
                salary_max=job.get("maxSalary"),
                experience_required=self._experience_range(job.get("minExp"), job.get("maxExp")),
            )
            for job in jobs
            if clean_text(job.get("title")) and clean_text(job.get("company", {}).get("name"))
        ]
        return limit_jobs_for_source(self.source_name, parsed_jobs)

    def parse(self, html: str) -> list[JobItem]:
        del html
        return []

    def _experience_range(self, min_exp: object, max_exp: object) -> str | None:
        if min_exp is None and max_exp is None:
            return None
        if min_exp is None:
            return f"up to {max_exp} years"
        if max_exp is None:
            return f"{min_exp}+ years"
        return f"{min_exp}-{max_exp} years"
