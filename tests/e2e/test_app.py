import unittest

from fastapi.testclient import TestClient

from app.main import app


class AppSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_auth_routes_are_registered(self) -> None:
        routes = {route.path for route in app.routes}

        self.assertIn("/api/v1/auth/register", routes)
        self.assertIn("/api/v1/auth/login", routes)
        self.assertIn("/api/v1/auth/refresh", routes)
        self.assertIn("/api/v1/auth/request-email-otp", routes)
        self.assertIn("/api/v1/auth/verify-email-otp", routes)
        self.assertIn("/api/v1/auth/contact-support", routes)
        self.assertIn("/api/v1/resumes/upload", routes)
        self.assertIn("/api/v1/resumes/", routes)
        self.assertIn("/api/v1/resumes/{resume_id}/status", routes)
        self.assertIn("/api/v1/resumes/{resume_id}", routes)
        self.assertIn("/api/v1/users/me", routes)
        self.assertIn("/api/v1/users/me/profile-completeness", routes)
        self.assertIn("/api/v1/users/me/github-scan", routes)
        self.assertIn("/api/v1/jobs/", routes)
        self.assertIn("/api/v1/jobs/manual", routes)
        self.assertIn("/api/v1/jobs/{job_id}", routes)
        self.assertIn("/api/v1/scraper/run", routes)
        self.assertIn("/api/v1/scraper/stop", routes)
        self.assertIn("/api/v1/scraper/status", routes)


if __name__ == "__main__":
    unittest.main()
