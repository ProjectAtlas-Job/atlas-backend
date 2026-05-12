from collections.abc import Callable

from app.db.models.user import User

MissingField = dict[str, object]


def _has_text_value(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _has_min_items(values: list[str] | None, minimum: int) -> bool:
    return values is not None and len(values) >= minimum


def compute_completeness(
    user: User,
    has_completed_resume: bool,
    gmail_connected: bool,
) -> tuple[int, list[MissingField]]:
    missing_fields: list[MissingField] = []
    total_score = 0

    llm_configured = False
    if user.settings is not None:
        llm_configured = user.settings.use_platform_api_key or user.settings.llm_api_key_encrypted is not None

    checks: list[tuple[str, int, str, bool | Callable[[], bool]]] = [
        ("full_name", 5, "/profile#full-name", _has_text_value(user.full_name)),
        ("phone", 5, "/profile#phone", _has_text_value(user.phone)),
        ("location", 5, "/profile#location", _has_text_value(user.location)),
        ("bio", 10, "/profile#bio", user.bio is not None and len(user.bio) > 50),
        ("resume", 20, "/profile#resumes", has_completed_resume),
        ("skills", 10, "/profile#skills", _has_min_items(user.skills, 4)),
        ("target_roles", 10, "/profile#target-roles", _has_min_items(user.target_roles, 2)),
        ("target_work_types", 5, "/profile#target-work-types", _has_min_items(user.target_work_types, 1)),
        ("linkedin_url", 5, "/profile#linkedin", _has_text_value(user.linkedin_url)),
        ("github", 10, "/profile#github", user.github_metadata is not None),
        ("gmail", 10, "/profile#gmail", gmail_connected),
        ("llm", 5, "/profile#llm", llm_configured),
    ]

    for field, points, action_url, passed in checks:
        if passed() if callable(passed) else passed:
            total_score += points
            continue
        missing_fields.append({"field": field, "points": points, "action_url": action_url})

    return total_score, missing_fields
