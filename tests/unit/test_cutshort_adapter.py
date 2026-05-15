from __future__ import annotations

import unittest

from app.services.scrapers.adapters.cutshort import CutshortAdapter


class CutshortAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = CutshortAdapter()

    def test_parse_listing_card_extracts_job_metadata(self) -> None:
        html = """
        <html>
          <body>
            <article class="job-card">
              <a href="/jobs/senior-python-engineer-12345">
                <h3>Senior Python Engineer</h3>
              </a>
              <div class="company-name">Atlas Labs</div>
              <div class="location">Bengaluru, India</div>
              <div class="salary">25,00,000 - 35,00,000</div>
              <div class="experience">3-5 years</div>
            </article>
          </body>
        </html>
        """

        jobs = self.adapter.parse(html)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Python Engineer")
        self.assertEqual(jobs[0].company, "Atlas Labs")
        self.assertEqual(jobs[0].location, "Bengaluru, India")
        self.assertEqual(jobs[0].source_url, "https://cutshort.io/jobs/senior-python-engineer-12345")
        self.assertEqual(jobs[0].salary_min, 2500000)
        self.assertEqual(jobs[0].salary_max, 3500000)
        self.assertEqual(jobs[0].experience_required, "3-5 years")

    def test_parse_prefers_json_ld_when_available(self) -> None:
        html = """
        <html>
          <head>
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "JobPosting",
                "title": "Backend Engineer",
                "description": "Build job systems",
                "url": "https://cutshort.io/jobs/backend-engineer",
                "datePosted": "2026-05-15",
                "employmentType": "FULL_TIME",
                "hiringOrganization": {"name": "Atlas Labs"},
                "jobLocation": {
                  "address": {
                    "addressLocality": "Pune",
                    "addressCountry": "India"
                  }
                }
              }
            </script>
          </head>
        </html>
        """

        jobs = self.adapter.parse(html)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Backend Engineer")
        self.assertEqual(jobs[0].company, "Atlas Labs")
        self.assertEqual(jobs[0].location, "Pune, India")
        self.assertEqual(jobs[0].work_type, ["full_time"])


if __name__ == "__main__":
    unittest.main()
