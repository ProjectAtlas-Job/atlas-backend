from __future__ import annotations

import asyncio
import math
import sys
import types
from importlib import import_module, reload

from app.services.resume.parser import extract_text, normalise_text
from app.services.resume.scorer import structural_score
from app.worker.tasks.resume import process_resume


def test_extract_text_decodes_utf8_for_plain_text() -> None:
    assert extract_text("hello\nworld".encode("utf-8"), "txt") == "hello\nworld"


def test_normalise_text_cleans_whitespace_and_non_printable_characters() -> None:
    raw = "  Jane\x00   Doe \n\n\tSenior\tEngineer \n\n skills   "
    assert normalise_text(raw) == "Jane Doe\n\nSenior Engineer\n\nskills"


def test_structural_score_counts_expected_sections() -> None:
    text = "Work Experience\nEducation\nTechnical Skills\nEmail"
    assert structural_score(text) == 1.0


def test_embed_truncates_and_normalizes_output(monkeypatch) -> None:
    module_name = "app.services.resume.embedder"
    sys.modules.pop(module_name, None)
    fake_sentence_transformers = types.ModuleType("sentence_transformers")

    captured: dict[str, object] = {}

    class FakeVector:
        def tolist(self) -> list[float]:
            return [0.25, 0.75]

    class FakeModel:
        def encode(self, text: str, normalize_embeddings: bool) -> FakeVector:
            captured["text"] = text
            captured["normalize_embeddings"] = normalize_embeddings
            return FakeVector()

    fake_sentence_transformers.SentenceTransformer = lambda name: FakeModel()
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_sentence_transformers)

    embedder = import_module(module_name)
    reload(embedder)

    result = embedder.embed("x" * 9000)

    assert result == [0.25, 0.75]
    assert captured["text"] == "x" * 8000
    assert captured["normalize_embeddings"] is True


def test_semantic_score_uses_cosine_similarity(monkeypatch) -> None:
    import app.services.resume.scorer as scorer

    scorer._reference_embedding.cache_clear()
    monkeypatch.setattr(scorer, "embed", lambda text: [1.0, 0.0])

    assert math.isclose(scorer.semantic_score("ignored", [1.0, 0.0]), 1.0)
    assert math.isclose(scorer.semantic_score("ignored", [0.0, 1.0]), 0.0)


def test_process_resume_persists_pipeline_outputs(monkeypatch) -> None:
    import app.worker.tasks.resume as worker_resume

    class FakeResume:
        def __init__(self) -> None:
            self.id = 7
            self.format = "txt"
            self.status = "pending"
            self.raw_text = None
            self.embedding = None
            self.structural_score = None
            self.semantic_score = None

    resume = FakeResume()

    class FakeResult:
        def scalar_one_or_none(self) -> FakeResume:
            return resume

    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0

        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def execute(self, query) -> FakeResult:
            return FakeResult()

        async def commit(self) -> None:
            self.commit_count += 1

        async def rollback(self) -> None:
            raise AssertionError("rollback should not be called on successful processing")

    fake_session = FakeSession()

    monkeypatch.setattr(worker_resume, "AsyncSessionLocal", lambda: fake_session)
    monkeypatch.setattr(worker_resume, "extract_text", lambda file_bytes, format: "raw text")
    monkeypatch.setattr(worker_resume, "normalise_text", lambda raw: "clean text")
    monkeypatch.setattr(worker_resume, "embed", lambda text: [0.1, 0.2])
    monkeypatch.setattr(worker_resume, "structural_score", lambda text: 0.75)
    monkeypatch.setattr(worker_resume, "semantic_score", lambda text, embedding: 0.5)

    asyncio.run(process_resume({}, resume_id=resume.id, file_bytes=b"hello"))

    assert resume.status == "completed"
    assert resume.raw_text == "clean text"
    assert resume.embedding == [0.1, 0.2]
    assert resume.structural_score == 0.75
    assert resume.semantic_score == 0.5
    assert fake_session.commit_count == 2
