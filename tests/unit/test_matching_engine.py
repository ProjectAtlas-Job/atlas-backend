import asyncio
import json
import unittest
from unittest.mock import patch

from app.services.matching.engine import make_job_matches_cache_key, serialize_cached_matches_payload
from app.worker.tasks.matching_tasks import refresh_job_matches


class FakeRedis:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.calls.append({"key": key, "value": value, "ex": ex})


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class MatchingEngineTests(unittest.TestCase):
    def test_serialize_cached_matches_payload_includes_items_and_timestamp(self) -> None:
        payload = json.loads(
            serialize_cached_matches_payload(
                [
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
                ]
            )
        )

        self.assertEqual(payload["items"][0]["job"]["title"], "Backend Engineer")
        self.assertEqual(payload["items"][0]["match_score"], 0.8123)
        self.assertTrue(payload["generated_at"])

    def test_make_job_matches_cache_key_uses_user_namespace(self) -> None:
        self.assertEqual(make_job_matches_cache_key(42), "user:42:job_matches")

    def test_refresh_job_matches_sets_cache(self) -> None:
        fake_redis = FakeRedis()

        async def fake_get_match_threshold(user_id: int, db) -> float:
            self.assertEqual(user_id, 42)
            return 0.7

        async def fake_get_job_matches(user_id: int, db, threshold: float = 0.65, limit: int = 50):
            self.assertEqual(user_id, 42)
            self.assertEqual(threshold, 0.7)
            self.assertEqual(limit, 50)
            return [
                {
                    "job": {
                        "id": 7,
                        "company_id": None,
                        "company_name_raw": "Atlas Labs",
                        "title": "Platform Engineer",
                        "description": "Scale matching",
                        "location": "Remote",
                        "work_type": ["remote"],
                        "salary_min": None,
                        "salary_max": None,
                        "experience_required": None,
                        "skills_required": ["python"],
                        "source": "naukri",
                        "source_url": "https://example.com/jobs/7",
                        "is_active": True,
                        "posted_at": None,
                        "scraped_at": "2026-05-15T12:00:00Z",
                    },
                    "match_score": 0.9012,
                }
            ]

        with (
            patch("app.worker.tasks.matching_tasks.AsyncSessionLocal", lambda: FakeSession()),
            patch("app.worker.tasks.matching_tasks.get_match_threshold", fake_get_match_threshold),
            patch("app.worker.tasks.matching_tasks.get_job_matches", fake_get_job_matches),
        ):
            result = asyncio.run(refresh_job_matches({"redis": fake_redis}, user_id=42))

        self.assertEqual(result, {"user_id": 42, "count": 1})
        self.assertEqual(fake_redis.calls[0]["key"], "user:42:job_matches")
        self.assertEqual(fake_redis.calls[0]["ex"], 86400)
        cached_payload = json.loads(fake_redis.calls[0]["value"])
        self.assertEqual(cached_payload["items"][0]["job"]["title"], "Platform Engineer")

    def test_refresh_job_matches_caches_empty_results(self) -> None:
        fake_redis = FakeRedis()

        async def fake_get_match_threshold(user_id: int, db) -> float:
            self.assertEqual(user_id, 99)
            return 0.65

        async def fake_get_job_matches(user_id: int, db, threshold: float = 0.65, limit: int = 50):
            self.assertEqual(user_id, 99)
            self.assertEqual(threshold, 0.65)
            self.assertEqual(limit, 50)
            return []

        with (
            patch("app.worker.tasks.matching_tasks.AsyncSessionLocal", lambda: FakeSession()),
            patch("app.worker.tasks.matching_tasks.get_match_threshold", fake_get_match_threshold),
            patch("app.worker.tasks.matching_tasks.get_job_matches", fake_get_job_matches),
        ):
            result = asyncio.run(refresh_job_matches({"redis": fake_redis}, user_id=99))

        self.assertEqual(result, {"user_id": 99, "count": 0})
        self.assertEqual(fake_redis.calls[0]["key"], "user:99:job_matches")
        self.assertEqual(fake_redis.calls[0]["ex"], 86400)
        cached_payload = json.loads(fake_redis.calls[0]["value"])
        self.assertEqual(cached_payload["items"], [])
        self.assertTrue(cached_payload["generated_at"])


if __name__ == "__main__":
    unittest.main()
