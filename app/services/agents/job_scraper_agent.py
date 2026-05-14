from __future__ import annotations

from functools import lru_cache
from typing import Any, TypedDict

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.db.session import AsyncSessionLocal
from app.services.llm import call_llm
from app.services.scrapers import get_adapter_for_domain, get_adapter_for_source
from app.services.scrapers.adapters.generic import JobListExtraction
from app.services.scrapers.base import JobItem
from app.services.scrapers.service import persist_scraped_jobs, update_scrape_action_log
from app.services.scrapers.utils import (
    clean_text,
    get_domain,
    html_to_visible_text,
    json_ld_job_postings,
    map_json_ld_to_job_item,
)


class JobScraperState(TypedDict):
    url: str
    source_type: str
    raw_html: str | None
    parsed_jobs: list[dict[str, Any]]
    saved_count: int
    task_id: str | None
    user_id: int | None
    error: str | None


async def fetch_page(state: JobScraperState) -> JobScraperState:
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(state["url"], wait_until="networkidle", timeout=30000)
                state["raw_html"] = await page.content()
                state["error"] = None
            finally:
                await browser.close()
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        state["error"] = f"Failed to fetch page: {exc}"
        state["raw_html"] = None
    return state


async def route_parser(state: JobScraperState) -> JobScraperState:
    state["error"] = state.get("error")
    return state


async def try_json_ld(state: JobScraperState) -> JobScraperState:
    html = state.get("raw_html") or ""
    parsed_jobs: list[dict[str, Any]] = []
    for item in json_ld_job_postings(html):
        job = map_json_ld_to_job_item(item, default_url=state["url"])
        if job is None:
            continue
        parsed_jobs.append(job_item_to_dict(job))
    state["parsed_jobs"] = parsed_jobs
    return state


async def site_specific_parse(state: JobScraperState) -> JobScraperState:
    domain = get_domain(state["url"])
    adapter = get_adapter_for_domain(domain)
    if adapter is None:
        source_hint = clean_text(state.get("source_type", "")).lower()
        if source_hint:
            adapter = get_adapter_for_source(source_hint)
    if adapter is None:
        state["error"] = f"No adapter available for domain '{domain}'."
        state["parsed_jobs"] = []
        return state
    if adapter.source_name == "hackernews":
        state["error"] = "HackerNews URLs must be handled by the REST adapter via fetch_jobs()."
        state["parsed_jobs"] = []
        return state

    html = state.get("raw_html") or ""
    try:
        jobs = adapter.parse(html)
    except Exception as exc:
        state["error"] = f"Adapter parse failed: {exc}"
        state["parsed_jobs"] = []
        return state

    state["parsed_jobs"] = [job_item_to_dict(job) for job in jobs]
    return state


async def ai_extraction(state: JobScraperState) -> JobScraperState:
    html = state.get("raw_html") or ""
    page_text = html_to_visible_text(html)[:15000]
    extraction = call_llm(page_text, response_model=JobListExtraction)
    parsed_jobs: list[dict[str, Any]] = []
    for job in extraction.jobs:
        parsed_jobs.append(
            job_item_to_dict(
                JobItem(
                    title=clean_text(job.title) or "Untitled role",
                    company=clean_text(job.company) or "Unknown company",
                    location=clean_text(job.location) or None,
                    description=clean_text(job.description) or clean_text(job.title),
                    work_type=list(job.work_type),
                    source_url=clean_text(job.source_url) or state["url"],
                    posted_at=clean_text(job.posted_at) or None,
                    salary_min=job.salary_min,
                    salary_max=job.salary_max,
                )
            )
        )
    state["parsed_jobs"] = parsed_jobs
    return state


async def embed_and_save(state: JobScraperState) -> JobScraperState:
    parsed_jobs = [job_item_from_dict(payload) for payload in state.get("parsed_jobs", [])]

    async with AsyncSessionLocal() as session:
        saved_count, skipped_count = await persist_scraped_jobs(
            db=session,
            jobs=parsed_jobs,
            source_type=clean_text(state.get("source_type")) or "scraper",
            user_id=state.get("user_id"),
        )
        await update_scrape_action_log(
            db=session,
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            status="success",
            message=None,
            metadata_updates={
                "task_id": state.get("task_id"),
                "url": state.get("url"),
                "source_type": state.get("source_type"),
                "saved_count": saved_count,
                "skipped_count": skipped_count,
            },
        )

    state["saved_count"] = saved_count
    return state


async def handle_error(state: JobScraperState) -> JobScraperState:
    async with AsyncSessionLocal() as session:
        await update_scrape_action_log(
            db=session,
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            metadata_updates={
                "task_id": state.get("task_id"),
                "url": state.get("url"),
                "source_type": state.get("source_type"),
            },
            status="failed",
            message=state.get("error"),
        )
    return state


def route_after_fetch(state: JobScraperState) -> str:
    if state.get("error"):
        return "handle_error"
    return "route_parser"


def route_by_source(state: JobScraperState) -> str:
    domain = get_domain(state["url"])
    adapter = get_adapter_for_domain(domain)
    if adapter is None:
        source_hint = clean_text(state.get("source_type", "")).lower()
        if source_hint:
            hinted = get_adapter_for_source(source_hint)
            if hinted.source_name != "scraper":
                adapter = hinted

    if adapter is not None and adapter.source_name != "scraper":
        if adapter.source_name == "hackernews":
            state["error"] = "HackerNews should be handled by adapter.fetch_jobs() instead of the HTML agent route."
            return "handle_error"
        return "site_specific_parse"
    return "try_json_ld"


def route_after_json_ld(state: JobScraperState) -> str:
    if state.get("parsed_jobs"):
        return "embed_and_save"
    return "ai_extraction"


def job_item_to_dict(job: JobItem) -> dict[str, Any]:
    return {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "work_type": list(job.work_type),
        "source_url": job.source_url,
        "posted_at": job.posted_at,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
    }


def job_item_from_dict(payload: dict[str, Any]) -> JobItem:
    return JobItem(
        title=clean_text(payload.get("title")) or "Untitled role",
        company=clean_text(payload.get("company")) or "Unknown company",
        location=clean_text(payload.get("location")) or None,
        description=clean_text(payload.get("description")) or clean_text(payload.get("title")),
        work_type=list(payload.get("work_type") or []),
        source_url=clean_text(payload.get("source_url")) or "",
        posted_at=clean_text(payload.get("posted_at")) or None,
        salary_min=payload.get("salary_min"),
        salary_max=payload.get("salary_max"),
    )


def build_job_scraper_graph():
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(JobScraperState)
    workflow.add_node("fetch_page", fetch_page)
    workflow.add_node("route_parser", route_parser)
    workflow.add_node("try_json_ld", try_json_ld)
    workflow.add_node("site_specific_parse", site_specific_parse)
    workflow.add_node("ai_extraction", ai_extraction)
    workflow.add_node("embed_and_save", embed_and_save)
    workflow.add_node("handle_error", handle_error)

    workflow.set_entry_point("fetch_page")
    workflow.add_conditional_edges("fetch_page", route_after_fetch)
    workflow.add_conditional_edges("route_parser", route_by_source)
    workflow.add_conditional_edges("try_json_ld", route_after_json_ld)
    workflow.add_edge("site_specific_parse", "embed_and_save")
    workflow.add_edge("ai_extraction", "embed_and_save")
    workflow.add_edge("embed_and_save", END)
    workflow.add_edge("handle_error", END)
    return workflow.compile()


@lru_cache(maxsize=1)
def get_job_scraper_app():
    return build_job_scraper_graph()


async def run_job_scraper_agent(
    *,
    url: str,
    source_type: str,
    user_id: int | None = None,
    task_id: str | None = None,
) -> JobScraperState:
    initial_state: JobScraperState = {
        "url": url,
        "source_type": source_type,
        "raw_html": None,
        "parsed_jobs": [],
        "saved_count": 0,
        "task_id": task_id,
        "user_id": user_id,
        "error": None,
    }
    return await get_job_scraper_app().ainvoke(initial_state)
