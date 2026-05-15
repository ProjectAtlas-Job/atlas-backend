import unittest

from pydantic import ValidationError

from app.schemas.job import JobListParams, JobMatchListRead


class JobListParamsSchemaTests(unittest.TestCase):
    def test_normalizes_blank_optional_values_to_none(self) -> None:
        payload = JobListParams(source="  ", location=" Bengaluru  ", search="  python backend ")

        self.assertIsNone(payload.source)
        self.assertEqual(payload.location, "Bengaluru")
        self.assertEqual(payload.search, "python backend")

    def test_rejects_limit_above_fifty(self) -> None:
        with self.assertRaises(ValidationError):
            JobListParams(limit=51)

    def test_job_match_list_parses_nested_job_payload(self) -> None:
        payload = JobMatchListRead.model_validate(
            {
                "items": [
                    {
                        "job": {
                            "id": 1,
                            "company_id": None,
                            "company_name_raw": "Atlas Labs",
                            "title": "Backend Engineer",
                            "description": "Build APIs",
                            "location": "Bengaluru",
                            "work_type": ["remote"],
                            "salary_min": None,
                            "salary_max": None,
                            "experience_required": None,
                            "skills_required": ["python"],
                            "source": "wellfound",
                            "source_url": "https://wellfound.com/jobs/1",
                            "is_active": True,
                            "posted_at": None,
                            "scraped_at": "2026-05-15T12:00:00Z",
                        },
                        "match_score": 0.8123,
                    }
                ],
                "cached": True,
                "generated_at": "2026-05-15T12:05:00Z",
            }
        )

        self.assertTrue(payload.cached)
        self.assertEqual(payload.items[0].job.title, "Backend Engineer")
        self.assertEqual(payload.items[0].match_score, 0.8123)
