import unittest
from types import SimpleNamespace

from app.core.constants import MAJOR_JOB_BOARDS, MINOR_JOB_BOARDS
from app.worker import scheduler as scheduler_module


class _FakeArqPool:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def enqueue_job(self, name: str, **kwargs: object) -> None:
        self.calls.append({"name": name, **kwargs})


class _FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self._rows)


class _FakeSession:
    def __init__(self, rows: list[object] | None = None) -> None:
        self.rows = rows or []
        self.statements: list[object] = []
        self.commits = 0

    async def execute(self, statement: object) -> _FakeResult:
        self.statements.append(statement)
        return _FakeResult(self.rows)

    async def commit(self) -> None:
        self.commits += 1


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        scheduler_module.clear_arq_pool()

    async def test_scrape_major_boards_enqueues_every_major_board(self) -> None:
        pool = _FakeArqPool()
        scheduler_module.bind_arq_pool(pool)

        await scheduler_module.scrape_major_boards()

        self.assertEqual(len(pool.calls), len(MAJOR_JOB_BOARDS))
        self.assertEqual(
            pool.calls,
            [
                {
                    "name": "scrape_job_board",
                    "url": board["url"],
                    "source_type": board["source_type"],
                }
                for board in MAJOR_JOB_BOARDS
            ],
        )

    async def test_scrape_minor_boards_enqueues_every_minor_board(self) -> None:
        pool = _FakeArqPool()
        scheduler_module.bind_arq_pool(pool)

        await scheduler_module.scrape_minor_boards()

        self.assertEqual(len(pool.calls), len(MINOR_JOB_BOARDS))
        self.assertEqual(
            pool.calls,
            [
                {
                    "name": "scrape_job_board",
                    "url": board["url"],
                    "source_type": board["source_type"],
                }
                for board in MINOR_JOB_BOARDS
            ],
        )

    async def test_user_configured_scraping_only_enqueues_valid_user_urls(self) -> None:
        pool = _FakeArqPool()
        fake_session = _FakeSession(
            rows=[
                SimpleNamespace(user_id=11, scrape_urls=[]),
                SimpleNamespace(
                    user_id=12,
                    scrape_urls=[
                        {"url": "https://example.com/jobs"},
                        {"url": "   "},
                        {"missing": "url"},
                        "not-a-dict",
                    ],
                ),
            ]
        )
        original_session_local = scheduler_module.AsyncSessionLocal
        scheduler_module.bind_arq_pool(pool)
        scheduler_module.AsyncSessionLocal = lambda: _FakeSessionContext(fake_session)

        try:
            await scheduler_module.user_configured_scraping()
        finally:
            scheduler_module.AsyncSessionLocal = original_session_local

        self.assertEqual(
            pool.calls,
            [
                {
                    "name": "scrape_job_board",
                    "url": "https://example.com/jobs",
                    "source_type": "scraper",
                    "user_id": 12,
                }
            ],
        )

    async def test_deactivate_stale_jobs_commits_update(self) -> None:
        fake_session = _FakeSession()
        original_session_local = scheduler_module.AsyncSessionLocal
        scheduler_module.AsyncSessionLocal = lambda: _FakeSessionContext(fake_session)

        try:
            await scheduler_module.deactivate_stale_jobs()
        finally:
            scheduler_module.AsyncSessionLocal = original_session_local

        self.assertEqual(len(fake_session.statements), 1)
        self.assertEqual(fake_session.commits, 1)

    async def test_rotate_api_keys_is_safe_when_model_is_unavailable(self) -> None:
        await scheduler_module.rotate_api_keys()


if __name__ == "__main__":
    unittest.main()
