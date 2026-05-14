from __future__ import annotations

import unittest
from pathlib import Path

from app.services.scrapers.adapters.internshala import InternshalaAdapter
from app.services.scrapers.adapters.naukri import NaukriAdapter
from app.services.scrapers.adapters.wellfound import WellfoundAdapter


FIXTURES_DIR = Path(__file__).parent / "scrapers" / "fixtures"


class _FakePage:
    def __init__(self, html: str) -> None:
        self.html = html
        self.goto_calls: list[dict[str, object]] = []

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})

    async def content(self) -> str:
        return self.html


class _FakeBrowser:
    def __init__(self, html: str) -> None:
        self.page = _FakePage(html)

    async def new_page(self) -> _FakePage:
        return self.page

    async def close(self) -> None:
        return None


class _FakeChromium:
    def __init__(self, html: str) -> None:
        self.browser = _FakeBrowser(html)

    async def launch(self, *, headless: bool) -> _FakeBrowser:
        assert headless is True
        return self.browser


class _FakePlaywrightManager:
    def __init__(self, html: str) -> None:
        self.chromium = _FakeChromium(html)

    async def __aenter__(self) -> "_FakePlaywrightManager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class AdapterFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_naukri_adapter_fetches_and_parses_json_ld_listing(self) -> None:
        fixture_html = (FIXTURES_DIR / "naukri_listing.html").read_text()
        adapter = NaukriAdapter()

        from app.services.scrapers.adapters import naukri as naukri_module

        original_async_playwright = naukri_module.async_playwright
        try:
            naukri_module.async_playwright = lambda: _FakePlaywrightManager(fixture_html)
            jobs = await adapter.fetch_jobs(
                "https://www.naukri.com/job-listings-senior-python-developer-atlas-fintech-bengaluru-123456"
            )
        finally:
            naukri_module.async_playwright = original_async_playwright

        self.assertGreater(len(jobs), 0)
        self.assertEqual(jobs[0].title, "Senior Python Developer")
        self.assertEqual(jobs[0].company, "Atlas Fintech")
        self.assertEqual(jobs[0].work_type, ["full_time"])
        self.assertTrue(jobs[0].source_url.startswith("https://www.naukri.com/job-listings"))

    async def test_internshala_adapter_fetches_and_parses_dom_listing(self) -> None:
        fixture_html = (FIXTURES_DIR / "internshala_listing.html").read_text()
        adapter = InternshalaAdapter()

        from app.services.scrapers.adapters import internshala as internshala_module

        original_async_playwright = internshala_module.async_playwright
        try:
            internshala_module.async_playwright = lambda: _FakePlaywrightManager(fixture_html)
            jobs = await adapter.fetch_jobs("https://internshala.com/internships")
        finally:
            internshala_module.async_playwright = original_async_playwright

        self.assertGreater(len(jobs), 0)
        self.assertEqual(jobs[0].title, "Customer Onboarding & Operations")
        self.assertEqual(jobs[0].company, "Dinematters")
        self.assertEqual(jobs[0].location, "Surat")
        self.assertEqual(jobs[0].work_type, ["internship"])
        self.assertEqual(jobs[0].salary_min, 72000)
        self.assertEqual(jobs[0].salary_max, 120000)

    async def test_wellfound_adapter_fetches_and_parses_india_listing(self) -> None:
        fixture_html = (FIXTURES_DIR / "wellfound_listing.html").read_text()
        adapter = WellfoundAdapter()

        from app.services.scrapers.adapters import wellfound as wellfound_module

        original_async_playwright = wellfound_module.async_playwright
        try:
            wellfound_module.async_playwright = lambda: _FakePlaywrightManager(fixture_html)
            jobs = await adapter.fetch_jobs("https://wellfound.com/jobs/123456-backend-engineer")
        finally:
            wellfound_module.async_playwright = original_async_playwright

        self.assertGreater(len(jobs), 0)
        self.assertEqual(jobs[0].title, "Backend Engineer")
        self.assertEqual(jobs[0].company, "Atlas Labs")
        self.assertIn("India", jobs[0].location or "")
        self.assertEqual(jobs[0].work_type, ["full_time"])


if __name__ == "__main__":
    unittest.main()
