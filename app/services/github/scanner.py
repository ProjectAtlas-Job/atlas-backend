from collections import Counter

import httpx


async def scan_github_repos(username: str, access_token: str) -> dict[str, object]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {access_token}",
    }
    url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        repos = response.json()

    recent_repos = repos[:30]
    language_counts: Counter[str] = Counter()
    topics: set[str] = set()
    top_repo_candidates: list[dict[str, object]] = []
    total_stars = 0

    for repo in recent_repos:
        language = repo.get("language")
        if isinstance(language, str) and language.strip():
            language_counts[language] += 1

        repo_topics = repo.get("topics", [])
        if isinstance(repo_topics, list):
            topics.update(topic for topic in repo_topics if isinstance(topic, str) and topic.strip())

        stars = int(repo.get("stargazers_count") or 0)
        total_stars += stars
        top_repo_candidates.append(
            {
                "name": repo.get("name"),
                "description": repo.get("description"),
                "language": language,
                "stars": stars,
            }
        )

    sorted_languages = dict(
        sorted(language_counts.items(), key=lambda item: (-item[1], item[0].lower()))
    )
    top_repos = sorted(
        top_repo_candidates,
        key=lambda repo: (-int(repo["stars"]), str(repo["name"]).lower()),
    )[:5]

    return {
        "languages": sorted_languages,
        "topics": sorted(topics, key=str.lower),
        "top_repos": top_repos,
        "total_stars": total_stars,
    }
