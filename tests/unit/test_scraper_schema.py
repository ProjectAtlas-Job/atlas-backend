import unittest

from pydantic import ValidationError

from app.schemas.job import JobPostingRead
from app.schemas.scraper import ManualJobSubmissionRequest, ScraperRunRequest
from app.services.scrapers.service import resolve_scraper_adapter


class ScraperSchemaTests(unittest.TestCase):
    def test_manual_job_submission_normalizes_whitespace(self) -> None:
        payload = ManualJobSubmissionRequest(url="  https://example.com/jobs/123  ")

        self.assertEqual(str(payload.url), "https://example.com/jobs/123")

    def test_scraper_run_rejects_unknown_target_type(self) -> None:
        with self.assertRaises(ValidationError):
            ScraperRunRequest(url="https://example.com/jobs/123", target_type="unknown")

    def test_job_posting_schema_normalizes_null_arrays(self) -> None:
        payload = JobPostingRead.model_validate(
            {
                "id": 1,
                "company_id": None,
                "company_name_raw": "Atlas Labs",
                "title": "Backend Engineer",
                "description": "Build APIs",
                "location": "Bengaluru",
                "work_type": None,
                "salary_min": None,
                "salary_max": None,
                "experience_required": None,
                "skills_required": None,
                "source": "wellfound",
                "source_url": "https://wellfound.com/jobs/123",
                "is_active": True,
                "posted_at": None,
                "scraped_at": "2026-05-14T12:00:00Z",
            }
        )

        self.assertEqual(payload.work_type, [])
        self.assertEqual(payload.skills_required, [])

    def test_manual_submission_uses_domain_adapter_when_available(self) -> None:
        adapter = resolve_scraper_adapter(
            url="https://wellfound.com/jobs/123456-backend-engineer",
            source_type="manual",
        )

        self.assertEqual(adapter.source_name, "wellfound")


if __name__ == "__main__":
    unittest.main()
