from __future__ import annotations

import asyncio
import json
import random
import re
from datetime import UTC, datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.core.constants import BOARD_RATE_LIMITS
from app.services.scrapers.base import JobItem

WORK_TYPE_ALIASES = {
    "full time": "full_time",
    "full-time": "full_time",
    "fulltime": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
    "parttime": "part_time",
    "internship": "internship",
    "intern": "internship",
    "contract": "contract",
    "contractor": "contract",
    "freelance": "freelance",
    "temporary": "contract",
}
ALLOWED_WORK_TYPES = {"full_time", "part_time", "internship", "contract", "freelance"}


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalise_work_types(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        candidates = [values]
    elif isinstance(values, list):
        candidates = [str(value) for value in values]
    else:
        candidates = [str(values)]

    normalized: list[str] = []
    for candidate in candidates:
        pieces = re.split(r"[,/|]+", candidate)
        for piece in pieces:
            lowered = clean_text(piece).lower()
            if not lowered:
                continue
            mapped = WORK_TYPE_ALIASES.get(lowered, lowered.replace(" ", "_").replace("-", "_"))
            if mapped in ALLOWED_WORK_TYPES and mapped not in normalized:
                normalized.append(mapped)
    return normalized


def limit_jobs_for_source(source_name: str, jobs: list[JobItem]) -> list[JobItem]:
    limits = BOARD_RATE_LIMITS.get(source_name, BOARD_RATE_LIMITS["default"])
    return jobs[: limits["max_jobs_per_run"]]


async def rate_limit_delay(source_name: str) -> None:
    limits = BOARD_RATE_LIMITS.get(source_name, BOARD_RATE_LIMITS["default"])
    delay = random.uniform(limits["min_delay_s"], limits["max_delay_s"])
    await asyncio.sleep(delay)


def extract_json_ld_items(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        content = script.string or script.get_text()
        if not content.strip():
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        items.extend(_flatten_json_ld(payload))
    return items


def _flatten_json_ld(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        flattened = [payload]
        if "@graph" in payload and isinstance(payload["@graph"], list):
            for item in payload["@graph"]:
                flattened.extend(_flatten_json_ld(item))
        return flattened
    if isinstance(payload, list):
        flattened: list[dict[str, Any]] = []
        for item in payload:
            flattened.extend(_flatten_json_ld(item))
        return flattened
    return []


def json_ld_job_postings(html: str) -> list[dict[str, Any]]:
    job_items: list[dict[str, Any]] = []
    for item in extract_json_ld_items(html):
        item_type = item.get("@type")
        if item_type == "JobPosting" or (isinstance(item_type, list) and "JobPosting" in item_type):
            job_items.append(item)
    return job_items


def extract_location(value: Any) -> str | None:
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                clean_text(address.get("addressLocality")),
                clean_text(address.get("addressRegion")),
                clean_text(address.get("addressCountry")),
            ]
            joined = ", ".join(part for part in parts if part)
            return joined or None
        name = clean_text(value.get("name"))
        if name:
            return name
    if isinstance(value, list):
        parts = [extract_location(item) for item in value]
        joined = ", ".join(part for part in parts if part)
        return joined or None
    text = clean_text(str(value)) if value is not None else ""
    return text or None


def map_json_ld_to_job_item(item: dict[str, Any], *, default_company: str = "", default_url: str = "") -> JobItem | None:
    title = clean_text(item.get("title"))
    company = clean_text(_extract_company_name(item)) or default_company
    description = clean_text(strip_tags(item.get("description", "")))
    source_url = clean_text(item.get("url")) or default_url
    if not title or not description or not source_url:
        return None
    return JobItem(
        title=title,
        company=company or "Unknown company",
        location=extract_location(item.get("jobLocation")),
        description=description,
        work_type=normalise_work_types(item.get("employmentType")),
        source_url=source_url,
        posted_at=clean_text(item.get("datePosted")) or None,
        salary_min=extract_salary_value(item, prefer="min"),
        salary_max=extract_salary_value(item, prefer="max"),
        experience_required=extract_experience_required(item),
    )


def _extract_company_name(item: dict[str, Any]) -> str | None:
    organization = item.get("hiringOrganization")
    if isinstance(organization, dict):
        return organization.get("name")
    return None


def extract_salary_value(item: dict[str, Any], *, prefer: str) -> int | None:
    salary = item.get("baseSalary")
    if not isinstance(salary, dict):
        return None
    value = salary.get("value")
    if isinstance(value, dict):
        raw = value.get(prefer) or value.get("value")
    else:
        raw = value
    if raw is None:
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def extract_experience_required(item: dict[str, Any]) -> str | None:
    experience = item.get("experienceRequirements")
    if isinstance(experience, dict):
        months = experience.get("monthsOfExperience")
        years = experience.get("yearsOfExperience")
        text = clean_text(experience.get("name") or experience.get("description"))
        if text:
            return text
        if months is not None:
            return f"{months} months"
        if years is not None:
            return f"{years} years"
        return None
    text = clean_text(str(experience)) if experience is not None else ""
    return text or None


def strip_tags(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def html_to_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return clean_text(soup.get_text(" ", strip=True))


def absolutize_url(url: str, base_url: str) -> str:
    return urljoin(base_url, url)


def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def parse_posted_at(value: str | None) -> datetime | None:
    if not value:
        return None
    text = clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_compensation_text(text: str, *, annualize_monthly: bool = False) -> tuple[int | None, int | None]:
    numbers = [int(value.replace(",", "")) for value in re.findall(r"[\d,]+", text or "")]
    if not numbers:
        return None, None

    multiplier = 12 if annualize_monthly else 1
    if len(numbers) >= 2:
        return numbers[0] * multiplier, numbers[1] * multiplier

    value = numbers[0] * multiplier
    return value, None


async def fetch_html_with_playwright(url: str, *, wait_after_load_ms: int = 3000) -> str:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1920,1080",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        page = await context.new_page()

        async def _abort_route(route) -> None:
            await route.abort()

        try:
            await page.route(re.compile(r".*\.(png|jpe?g|gif|svg|ico|woff2?)($|\?)", re.IGNORECASE), _abort_route)
            await page.route(re.compile(r".*(ads|analytics|tracking|pixel).*", re.IGNORECASE), _abort_route)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(wait_after_load_ms)
            except PlaywrightTimeoutError:
                await page.goto(url, wait_until="commit", timeout=30000)
                await page.wait_for_timeout(5000)
            return await page.content()
        finally:
            await browser.close()
