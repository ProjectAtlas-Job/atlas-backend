from __future__ import annotations

import unittest
from pathlib import Path

from app.services.agents.job_scraper_agent import route_after_fetch, route_after_json_ld, route_by_source, site_specific_parse, try_json_ld


FIXTURES_DIR = Path(__file__).parent / "scrapers" / "fixtures"


class JobScraperAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_route_after_fetch_handles_errors(self) -> None:
        state = {
            "url": "https://example.com/job",
            "source_type": "manual",
            "raw_html": None,
            "parsed_jobs": [],
            "saved_count": 0,
            "user_id": None,
            "error": "timeout",
        }
        self.assertEqual(route_after_fetch(state), "handle_error")

    def test_route_by_source_prefers_registered_domain(self) -> None:
        state = {
            "url": "https://internshala.com/internships",
            "source_type": "manual",
            "raw_html": "<html></html>",
            "parsed_jobs": [],
            "saved_count": 0,
            "user_id": None,
            "error": None,
        }
        self.assertEqual(route_by_source(state), "site_specific_parse")

    async def test_try_json_ld_extracts_job_postings_from_fixture(self) -> None:
        html = (FIXTURES_DIR / "naukri_listing.html").read_text()
        state = {
            "url": "https://www.naukri.com/job-listings-senior-python-developer-atlas-fintech-bengaluru-123456",
            "source_type": "naukri",
            "raw_html": html,
            "parsed_jobs": [],
            "saved_count": 0,
            "user_id": None,
            "error": None,
        }

        updated = await try_json_ld(state)
        self.assertEqual(len(updated["parsed_jobs"]), 1)
        self.assertEqual(updated["parsed_jobs"][0]["title"], "Senior Python Developer")
        self.assertEqual(route_after_json_ld(updated), "embed_and_save")

    async def test_site_specific_parse_uses_adapter_parse_for_html(self) -> None:
        html = (FIXTURES_DIR / "internshala_listing.html").read_text()
        state = {
            "url": "https://internshala.com/internships",
            "source_type": "internshala",
            "raw_html": html,
            "parsed_jobs": [],
            "saved_count": 0,
            "user_id": None,
            "error": None,
        }

        updated = await site_specific_parse(state)
        self.assertGreater(len(updated["parsed_jobs"]), 0)
        self.assertEqual(updated["parsed_jobs"][0]["company"], "Dinematters")
        self.assertEqual(updated["parsed_jobs"][0]["work_type"], ["internship"])


if __name__ == "__main__":
    unittest.main()
