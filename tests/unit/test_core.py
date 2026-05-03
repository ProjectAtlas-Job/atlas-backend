import unittest

from app.core.encryption import decrypt, encrypt
from app.core.security import hash_password, verify_password


class SecurityTests(unittest.TestCase):
    def test_password_hashing_round_trip(self) -> None:
        plain = "atlas-password"
        hashed = hash_password(plain)

        self.assertNotEqual(plain, hashed)
        self.assertTrue(verify_password(plain, hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_encryption_round_trip(self) -> None:
        value = "super-secret-token"
        encrypted = encrypt(value)

        self.assertNotEqual(value, encrypted)
        self.assertEqual(value, decrypt(encrypted))


if __name__ == "__main__":
    unittest.main()
