import unittest

from app.db.models.user import User
from app.db.models.user_settings import UserSettings
from app.services.profile.completeness import compute_completeness


class ProfileCompletenessTests(unittest.TestCase):
    def test_compute_completeness_returns_full_score_when_everything_is_present(self) -> None:
        user = User(
            email="user@example.com",
            full_name="Atlas User",
            phone="+1-555-0100",
            location="New York, NY",
            bio="Experienced backend engineer building resilient job search workflows for modern teams.",
            linkedin_url="https://linkedin.com/in/atlas",
            skills=["python", "fastapi", "sqlalchemy", "postgres"],
            target_roles=["Backend Engineer", "Platform Engineer"],
            target_work_types=["full-time"],
            github_metadata={"synced": True},
        )
        user.settings = UserSettings(use_platform_api_key=True, gmail_access_token_encrypted="token")

        score, missing = compute_completeness(
            user=user,
            has_completed_resume=True,
            gmail_connected=True,
        )

        self.assertEqual(score, 100)
        self.assertEqual(missing, [])

    def test_compute_completeness_returns_missing_fields_for_unmet_criteria(self) -> None:
        user = User(
            email="user@example.com",
            full_name="",
            phone=None,
            location=None,
            bio="Too short",
            linkedin_url=None,
            skills=["python", "fastapi", "sqlalchemy"],
            target_roles=["Backend Engineer"],
            target_work_types=[],
            github_metadata=None,
        )
        user.settings = UserSettings(use_platform_api_key=False, llm_api_key_encrypted=None)

        score, missing = compute_completeness(
            user=user,
            has_completed_resume=False,
            gmail_connected=False,
        )

        self.assertEqual(score, 0)
        self.assertEqual(
            missing,
            [
                {"field": "full_name", "points": 5, "action_url": "/profile#full-name"},
                {"field": "phone", "points": 5, "action_url": "/profile#phone"},
                {"field": "location", "points": 5, "action_url": "/profile#location"},
                {"field": "bio", "points": 10, "action_url": "/profile#bio"},
                {"field": "resume", "points": 20, "action_url": "/profile#resumes"},
                {"field": "skills", "points": 10, "action_url": "/profile#skills"},
                {"field": "target_roles", "points": 10, "action_url": "/profile#target-roles"},
                {"field": "target_work_types", "points": 5, "action_url": "/profile#target-work-types"},
                {"field": "linkedin_url", "points": 5, "action_url": "/profile#linkedin"},
                {"field": "github", "points": 10, "action_url": "/profile#github"},
                {"field": "gmail", "points": 10, "action_url": "/profile#gmail"},
                {"field": "llm", "points": 5, "action_url": "/profile#llm"},
            ],
        )
