import unittest

from pydantic import ValidationError

from app.schemas.scraper import ManualJobSubmissionRequest, ScraperRunRequest


class ScraperSchemaTests(unittest.TestCase):
    def test_manual_job_submission_normalizes_whitespace(self) -> None:
        payload = ManualJobSubmissionRequest(url="  https://example.com/jobs/123  ")

        self.assertEqual(str(payload.url), "https://example.com/jobs/123")

    def test_scraper_run_rejects_unknown_target_type(self) -> None:
        with self.assertRaises(ValidationError):
            ScraperRunRequest(url="https://example.com/jobs/123", target_type="unknown")


if __name__ == "__main__":
    unittest.main()
