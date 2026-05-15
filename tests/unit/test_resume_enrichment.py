import asyncio
import unittest
from unittest.mock import patch

from app.services.resume.llm_enricher import ResumeParseOutput, enrich_resume_with_llm
from app.worker.tasks.resume_tasks import process_resume


class ResumeEnrichmentTests(unittest.TestCase):
    def test_enrich_resume_with_llm_returns_structured_output(self) -> None:
        async def run() -> ResumeParseOutput:
            user_settings = object()
            with patch(
                "app.services.resume.llm_enricher.call_llm",
                return_value=ResumeParseOutput(
                    skills=["python"],
                    recent_role="Engineer at Atlas",
                    education="B.Tech at Example University",
                    top_projects=["Atlas matching engine"],
                    certifications=[],
                    experience_years=2,
                    ats_score=81.0,
                    ats_reasoning="Good section structure and measurable experience.",
                ),
            ):
                return await enrich_resume_with_llm("resume text", user_settings)

        result = asyncio.run(run())

        self.assertEqual(result.skills, ["python"])
        self.assertEqual(result.ats_score, 81.0)

    def test_process_resume_keeps_completed_status_when_llm_fails(self) -> None:
        import app.worker.tasks.resume_tasks as worker_resume

        class FakeResume:
            def __init__(self) -> None:
                self.id = 41
                self.user_id = 8
                self.status = "pending"
                self.updated_at = None
                self.raw_text = None
                self.embedding = None
                self.structural_score = None
                self.semantic_score = None
                self.parsed_json = None
                self.ats_score = None

        class FakeResult:
            def __init__(self, resume: FakeResume) -> None:
                self.resume = resume

            def scalar_one_or_none(self) -> FakeResume:
                return self.resume

        class FakeSession:
            def __init__(self, resume: FakeResume) -> None:
                self.resume = resume

            async def __aenter__(self) -> "FakeSession":
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def execute(self, query):
                return FakeResult(self.resume)

            async def commit(self) -> None:
                return None

            async def flush(self) -> None:
                return None

            async def rollback(self) -> None:
                raise AssertionError("rollback should not be called for LLM-only failures")

        resume = FakeResume()
        warnings: list[str] = []

        async def fake_settings(session, resume_id: int):
            self.assertEqual(resume_id, 41)
            return object()

        async def fake_enrich(raw_text: str, user_settings: object):
            raise RuntimeError("provider unavailable")

        async def fake_refresh(session, *, user_id: int):
            self.assertEqual(user_id, 8)
            return None

        with (
            patch.object(worker_resume, "AsyncSessionLocal", lambda: FakeSession(resume)),
            patch.object(worker_resume, "extract_text", lambda file_bytes, format: "raw text"),
            patch.object(worker_resume, "normalise_text", lambda raw: "clean text"),
            patch.object(worker_resume, "embed", lambda text: [0.1, 0.2]),
            patch.object(worker_resume, "structural_score", lambda text: 0.75),
            patch.object(worker_resume, "semantic_score", lambda text, embedding: 0.5),
            patch.object(worker_resume, "get_user_settings_for_resume", fake_settings),
            patch.object(worker_resume, "enrich_resume_with_llm", fake_enrich),
            patch.object(worker_resume, "refresh_profile_completeness", fake_refresh),
            patch.object(worker_resume.logger, "warning", lambda message, *args: warnings.append(message.format(*args))),
        ):
            result = asyncio.run(process_resume({}, resume_id=41, file_bytes=b"hello", filename="resume.txt"))

        self.assertEqual(resume.status, "completed")
        self.assertEqual(resume.parsed_json, None)
        self.assertEqual(resume.ats_score, None)
        self.assertTrue(warnings)
        self.assertEqual(result, {"resume_id": 41, "status": "completed"})


if __name__ == "__main__":
    unittest.main()
