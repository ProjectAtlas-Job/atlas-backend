from __future__ import annotations

import unittest

from pydantic import BaseModel

from app.services.llm import call_llm
from app.services.scrapers import get_adapter_for_source, get_adapter_for_url


class SkillsExtractionModel(BaseModel):
    skills: list[str]


class ScraperRuntimeTests(unittest.TestCase):
    def test_registry_resolves_new_board_adapters(self) -> None:
        self.assertEqual(get_adapter_for_source("cutshort").source_name, "cutshort")
        self.assertEqual(get_adapter_for_source("unstop").source_name, "unstop")
        self.assertEqual(get_adapter_for_url("https://www.iimjobs.com/j/technology").source_name, "iimjobs")
        self.assertEqual(get_adapter_for_url("https://www.hirist.tech/jobs").source_name, "hirist")

    def test_skills_extraction_heuristic_returns_normalized_tags(self) -> None:
        output = call_llm(
            "We need Python, FastAPI, PostgreSQL, Docker and AWS experience.",
            response_model=SkillsExtractionModel,
            temperature=0.0,
        )

        self.assertIn("python", output.skills)
        self.assertIn("fastapi", output.skills)
        self.assertIn("postgres", output.skills)
        self.assertIn("docker", output.skills)
        self.assertIn("aws", output.skills)


if __name__ == "__main__":
    unittest.main()
