import unittest

from app.services.email.templates import otp_email, password_reset_email, verification_email, welcome_email


class EmailTemplateTests(unittest.TestCase):
    def test_verification_email_contains_call_to_action(self) -> None:
        content = verification_email(full_name="Taylor", verification_link="https://example.com/verify")

        self.assertIn("Verify your Project Atlas email", content.subject)
        self.assertIn("https://example.com/verify", content.html)
        self.assertIn("Verify your Project Atlas email", content.text)

    def test_otp_email_contains_code(self) -> None:
        content = otp_email(full_name="Taylor", otp_code="123456")

        self.assertIn("123456", content.html)
        self.assertIn("123456", content.text)

    def test_password_reset_email_contains_link(self) -> None:
        content = password_reset_email(full_name="Taylor", reset_link="https://example.com/reset")

        self.assertIn("https://example.com/reset", content.html)
        self.assertIn("https://example.com/reset", content.text)

    def test_welcome_email_contains_dashboard_link(self) -> None:
        content = welcome_email(full_name="Taylor", dashboard_link="https://example.com/dashboard")

        self.assertIn("Welcome to Project Atlas", content.subject)
        self.assertIn("https://example.com/dashboard", content.html)


if __name__ == "__main__":
    unittest.main()
