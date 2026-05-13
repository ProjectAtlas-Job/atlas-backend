import unittest

from pydantic import ValidationError

from app.schemas.user import UserUpdate


class UserUpdateSchemaTests(unittest.TestCase):
    def test_user_update_normalizes_skills_to_lowercase(self) -> None:
        payload = UserUpdate(skills=["Python", " FASTAPI ", "SQLAlchemy"])

        self.assertEqual(payload.skills, ["python", "fastapi", "sqlalchemy"])

    def test_user_update_rejects_invalid_experience_level(self) -> None:
        with self.assertRaises(ValidationError):
            UserUpdate(experience_level="staff")

    def test_user_update_rejects_invalid_work_type(self) -> None:
        with self.assertRaises(ValidationError):
            UserUpdate(target_work_types=["full_time", "temporary"])

    def test_user_update_rejects_more_than_ten_target_roles(self) -> None:
        with self.assertRaises(ValidationError):
            UserUpdate(target_roles=[f"Role {index}" for index in range(11)])
