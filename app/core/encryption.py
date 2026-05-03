from cryptography.fernet import Fernet

from app.core.config import settings

SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "llm_api_key_encrypted",
        "smtp_password_encrypted",
        "gmail_access_token_encrypted",
        "gmail_refresh_token_encrypted",
    }
)


def _get_fernet() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode())


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()
