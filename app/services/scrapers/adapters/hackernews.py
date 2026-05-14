from __future__ import annotations

from typing import Any

import httpx

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import clean_text, strip_tags


SEARCH_URL = "https://hn.algolia.com/api/v1/search?query=who+is+hiring&tags=ask_hn&hitsPerPage=100"


class HackerNewsAdapter(BaseJobAdapter):
    source_name = "hackernews"
    domains = ["hn.algolia.com", "news.ycombinator.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url or SEARCH_URL)
            response.raise_for_status()
            payload = response.json()
            hits = payload.get("hits", [])
            story_id = self._latest_story_id(hits)
            if story_id is None:
                return [self._map_story_hit(hit) for hit in hits if self._map_story_hit(hit) is not None]

            comments_response = await client.get(
                f"https://hn.algolia.com/api/v1/search_by_date?tags=comment,story_{story_id}&hitsPerPage=500"
            )
            comments_response.raise_for_status()
            comment_hits = comments_response.json().get("hits", [])
        return [job for hit in comment_hits if (job := self._map_comment_hit(hit)) is not None]

    def parse(self, html: str) -> list[JobItem]:
        del html
        return []

    def _latest_story_id(self, hits: list[dict[str, Any]]) -> int | None:
        story_ids = [hit.get("story_id") or hit.get("objectID") for hit in hits if "story" in hit.get("_tags", [])]
        if not story_ids:
            return None
        return int(max(int(story_id) for story_id in story_ids))

    def _map_comment_hit(self, hit: dict[str, Any]) -> JobItem | None:
        raw_text = strip_tags(hit.get("comment_text") or "")
        if not raw_text:
            return None
        company, title = self._extract_company_and_title(raw_text)
        return JobItem(
            title=title or "Who's Hiring",
            company=company or "Unknown company",
            location=None,
            description=clean_text(raw_text),
            work_type=[],
            source_url=f"https://news.ycombinator.com/item?id={hit['objectID']}",
            posted_at=hit.get("created_at"),
            salary_min=None,
            salary_max=None,
        )

    def _map_story_hit(self, hit: dict[str, Any]) -> JobItem | None:
        title = clean_text(hit.get("title"))
        if not title:
            return None
        return JobItem(
            title=title,
            company="Hacker News",
            location=None,
            description=clean_text(strip_tags(hit.get("story_text") or "")) or title,
            work_type=[],
            source_url=f"https://news.ycombinator.com/item?id={hit['objectID']}",
            posted_at=hit.get("created_at"),
            salary_min=None,
            salary_max=None,
        )

    def _extract_company_and_title(self, text: str) -> tuple[str | None, str | None]:
        first_line = clean_text(text.splitlines()[0] if text.splitlines() else text)
        if " is hiring" in first_line.lower():
            company, _, remainder = first_line.partition(" is hiring")
            return clean_text(company), clean_text(remainder.lstrip(": -")) or None
        if ":" in first_line:
            company, _, title = first_line.partition(":")
            return clean_text(company), clean_text(title)
        return None, first_line or None
