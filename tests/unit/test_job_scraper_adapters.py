from __future__ import annotations

import unittest
from pathlib import Path

from app.services.scrapers.adapters.hirist import HiristAdapter
from app.services.scrapers.adapters.iimjobs import IIMJobsAdapter
from app.services.scrapers.adapters.internshala import InternshalaAdapter
from app.services.scrapers.adapters.naukri import NaukriAdapter
from app.services.scrapers.adapters.wellfound import WellfoundAdapter


FIXTURES_DIR = Path(__file__).parent / "scrapers" / "fixtures"


class AdapterFixtureTests(unittest.TestCase):
    def test_naukri_adapter_parses_json_ld_listing(self) -> None:
        fixture_html = (FIXTURES_DIR / "naukri_listing.html").read_text()
        jobs = NaukriAdapter().parse(fixture_html)

        self.assertGreater(len(jobs), 0)
        self.assertEqual(jobs[0].title, "Senior Python Developer")
        self.assertEqual(jobs[0].company, "Atlas Fintech")
        self.assertEqual(jobs[0].work_type, ["full_time"])
        self.assertTrue(jobs[0].source_url.startswith("https://www.naukri.com/job-listings"))

    def test_internshala_adapter_parses_dom_listing(self) -> None:
        fixture_html = (FIXTURES_DIR / "internshala_listing.html").read_text()
        jobs = InternshalaAdapter().parse(fixture_html)

        self.assertGreater(len(jobs), 0)
        self.assertEqual(jobs[0].title, "Customer Onboarding & Operations")
        self.assertEqual(jobs[0].company, "Dinematters")
        self.assertEqual(jobs[0].location, "Surat")
        self.assertEqual(jobs[0].work_type, ["internship"])
        self.assertEqual(jobs[0].salary_min, 72000)
        self.assertEqual(jobs[0].salary_max, 120000)

    def test_wellfound_adapter_parses_india_listing(self) -> None:
        fixture_html = (FIXTURES_DIR / "wellfound_listing.html").read_text()
        jobs = WellfoundAdapter().parse(fixture_html)

        self.assertGreater(len(jobs), 0)
        self.assertEqual(jobs[0].title, "Backend Engineer")
        self.assertEqual(jobs[0].company, "Atlas Labs")
        self.assertIn("India", jobs[0].location or "")
        self.assertEqual(jobs[0].work_type, ["full_time"])

    def test_iimjobs_adapter_parses_minimal_html(self) -> None:
        html = """
        <div class="job-container">
          <h2><a href="/jobs/backend-engineer">Backend Engineer</a></h2>
          <div class="company-name">Atlas Labs</div>
          <div class="job-location">Bengaluru</div>
        </div>
        """
        jobs = IIMJobsAdapter().parse(html)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Atlas Labs")
        self.assertEqual(jobs[0].location, "Bengaluru")

    def test_hirist_adapter_parses_minimal_html(self) -> None:
        html = """
        <article>
          <h2><a href="/job/backend-engineer">Backend Engineer</a></h2>
          <div class="company-name">Atlas Labs</div>
          <div class="job-location">Remote</div>
          <div class="experience">2-5 years</div>
        </article>
        """
        jobs = HiristAdapter().parse(html)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].experience_required, "2-5 years")
        self.assertTrue(jobs[0].source_url.startswith("https://www.hirist.tech"))


if __name__ == "__main__":
    unittest.main()
