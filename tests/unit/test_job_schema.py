import unittest

from pydantic import ValidationError

from app.schemas.job import JobListParams


class JobListParamsSchemaTests(unittest.TestCase):
    def test_normalizes_blank_optional_values_to_none(self) -> None:
        payload = JobListParams(source="  ", location=" Bengaluru  ", search="  python backend ")

        self.assertIsNone(payload.source)
        self.assertEqual(payload.location, "Bengaluru")
        self.assertEqual(payload.search, "python backend")

    def test_rejects_limit_above_fifty(self) -> None:
        with self.assertRaises(ValidationError):
            JobListParams(limit=51)
