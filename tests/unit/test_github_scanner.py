import unittest

from app.services.github import scanner


class _FakeResponse:
    def __init__(self, payload: list[dict[str, object]]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, object]]:
        return self.payload


class _FakeAsyncClient:
    def __init__(self, *, payload: list[dict[str, object]]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, headers: dict[str, str]) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers})
        return _FakeResponse(self.payload)


class GitHubScannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_github_repos_aggregates_languages_topics_and_stars(self) -> None:
        repos = [
            {
                "name": "atlas-api",
                "description": "Backend",
                "language": "Python",
                "topics": ["fastapi", "backend"],
                "stargazers_count": 8,
            },
            {
                "name": "atlas-web",
                "description": "Frontend",
                "language": "TypeScript",
                "topics": ["nextjs", "frontend", "backend"],
                "stargazers_count": 12,
            },
            {
                "name": "atlas-worker",
                "description": None,
                "language": "Python",
                "topics": [],
                "stargazers_count": 5,
            },
        ]
        captured_client: _FakeAsyncClient | None = None

        def fake_async_client(*, timeout: float) -> _FakeAsyncClient:
            nonlocal captured_client
            self.assertEqual(timeout, 30.0)
            captured_client = _FakeAsyncClient(payload=repos)
            return captured_client

        original_async_client = scanner.httpx.AsyncClient
        try:
            scanner.httpx.AsyncClient = fake_async_client
            result = await scanner.scan_github_repos("atlas-user", "token-123")
        finally:
            scanner.httpx.AsyncClient = original_async_client

        assert captured_client is not None
        self.assertEqual(len(captured_client.calls), 1)
        self.assertEqual(
            captured_client.calls[0]["url"],
            "https://api.github.com/users/atlas-user/repos?per_page=100&sort=updated",
        )
        self.assertEqual(
            captured_client.calls[0]["headers"]["Authorization"],
            "Bearer token-123",
        )
        self.assertEqual(result["languages"], {"Python": 2, "TypeScript": 1})
        self.assertEqual(result["topics"], ["backend", "fastapi", "frontend", "nextjs"])
        self.assertEqual(result["total_stars"], 25)
        self.assertEqual(
            result["top_repos"],
            [
                {
                    "name": "atlas-web",
                    "description": "Frontend",
                    "language": "TypeScript",
                    "stars": 12,
                },
                {
                    "name": "atlas-api",
                    "description": "Backend",
                    "language": "Python",
                    "stars": 8,
                },
                {
                    "name": "atlas-worker",
                    "description": None,
                    "language": "Python",
                    "stars": 5,
                },
            ],
        )

    async def test_scan_github_repos_limits_processing_to_thirty_recent_repositories(self) -> None:
        repos = [
            {
                "name": f"repo-{index}",
                "description": None,
                "language": "Python",
                "topics": [f"topic-{index}"],
                "stargazers_count": 1,
            }
            for index in range(35)
        ]

        def fake_async_client(*, timeout: float) -> _FakeAsyncClient:
            self.assertEqual(timeout, 30.0)
            return _FakeAsyncClient(payload=repos)

        original_async_client = scanner.httpx.AsyncClient
        try:
            scanner.httpx.AsyncClient = fake_async_client
            result = await scanner.scan_github_repos("atlas-user", "token-123")
        finally:
            scanner.httpx.AsyncClient = original_async_client

        self.assertEqual(result["languages"], {"Python": 30})
        self.assertEqual(result["total_stars"], 30)
        self.assertEqual(len(result["topics"]), 30)
        self.assertEqual(len(result["top_repos"]), 5)


if __name__ == "__main__":
    unittest.main()
