from __future__ import annotations

import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import absolutize_url, clean_text


class InternshalaAdapter(BaseJobAdapter):
    source_name = "internshala"
    domains = ["internshala.com", "www.internshala.com"]

    async def fetch_jobs(self, url: str, keywords: list[str] | None = None) -> list[JobItem]:
        del keywords
        html = await self._fetch_page_content(url)
        return self.parse(html)

    def parse(self, html: str) -> list[JobItem]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobItem] = []
        for card in soup.select(".individual_internship, .internship_meta"):
            container = card if "individual_internship" in (card.get("class") or []) else card.parent
            if container is None:
                continue
            title_tag = container.select_one(".job-title-href, .profile a")
            company_tag = container.select_one(".company_name .company-name, .company_name, .company-name")
            location_tags = container.select(".locations a, .location_link, .location_names a")
            description_tag = container.select_one(".about_job .text, .internship_other_details_container")

            title = clean_text(title_tag.get_text(" ", strip=True) if title_tag else "")
            company = clean_text(company_tag.get_text(" ", strip=True) if company_tag else "")
            source_href = ""
            if title_tag and title_tag.get("href"):
                source_href = str(title_tag["href"])
            elif container.get("data-href"):
                source_href = str(container["data-href"])
            source_url = absolutize_url(source_href, "https://internshala.com")
            if not title or not company or not source_href:
                continue

            location = ", ".join(
                clean_text(tag.get_text(" ", strip=True))
                for tag in location_tags
                if clean_text(tag.get_text(" ", strip=True))
            ) or None
            description = clean_text(description_tag.get_text(" ", strip=True) if description_tag else "")
            if not description:
                description = title

            salary_text = clean_text(container.select_one(".stipend").get_text(" ", strip=True) if container.select_one(".stipend") else "")
            salary_min, salary_max = self._parse_monthly_stipend(salary_text)

            posted_text = clean_text(
                container.select_one(".status-inactive span").get_text(" ", strip=True)
                if container.select_one(".status-inactive span")
                else ""
            )
            jobs.append(
                JobItem(
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    work_type=["internship"],
                    source_url=source_url,
                    posted_at=posted_text or None,
                    salary_min=salary_min,
                    salary_max=salary_max,
                )
            )
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

    def _parse_monthly_stipend(self, stipend_text: str) -> tuple[int | None, int | None]:
        sanitized = stipend_text.replace("/month", "").replace("per month", "")
        matches = [int(value.replace(",", "")) for value in re.findall(r"([\d,]+)", sanitized)]
        if len(matches) >= 2:
            return matches[0] * 12, matches[1] * 12
        if len(matches) == 1:
            yearly = matches[0] * 12
            return yearly, yearly
        return None, None
