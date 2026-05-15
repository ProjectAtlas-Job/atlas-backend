from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, limit_jobs_for_source, rate_limit_delay


class HackerNewsAdapter(BaseJobAdapter):
    source_name = "hackernews"
    domains = ["hn.algolia.com", "news.ycombinator.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del url, keywords
        await rate_limit_delay(self.source_name)
        async with httpx.AsyncClient(timeout=30.0) as client:
            search_response = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": "who is hiring", "tags": "ask_hn", "hitsPerPage": 1},
            )
            search_response.raise_for_status()
            search_data = search_response.json()
            hits = search_data.get("hits", [])
            if not hits:
                return []

            post_id = hits[0]["objectID"]
            comments_response = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"tags": f"comment,story_{post_id}", "hitsPerPage": 100},
            )
            comments_response.raise_for_status()
            comments = comments_response.json().get("hits", [])

        jobs = []
        for comment in comments:
            text = comment.get("comment_text", "") or comment.get("title", "")
            if not text or len(text) < 50:
                continue
            parsed = self._parse_hn_comment(text, comment["objectID"], comment.get("created_at"))
            if parsed:
                jobs.append(parsed)
        return limit_jobs_for_source(self.source_name, jobs)

    def parse(self, html: str) -> list[JobItem]:
        del html
        return []

    def _parse_hn_comment(self, text: str, comment_id: str, posted_at: str | None) -> JobItem | None:
        clean_text_value = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        if not clean_text_value:
            return None

        pipe_parts = [part.strip() for part in clean_text_value.split("|")]
        company = pipe_parts[0] if pipe_parts else "Unknown"
        company = re.sub(r"\s*\(.*?\)", "", company).strip() or "Unknown"
        title = pipe_parts[1] if len(pipe_parts) > 1 else "Software Engineer"
        location = pipe_parts[2] if len(pipe_parts) > 2 else None

        work_type = ["full_time"]

        return JobItem(
            title=clean_text(title)[:200] or "Software Engineer",
            company=clean_text(company)[:200] or "Unknown",
            location=clean_text(location) or None,
            description=clean_text(clean_text_value)[:3000],
            work_type=work_type,
            source_url=f"https://news.ycombinator.com/item?id={comment_id}",
            posted_at=posted_at,
            salary_min=None,
            salary_max=None,
            experience_required=None,
        )
