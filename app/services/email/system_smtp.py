import asyncio
import smtplib
from email.message import EmailMessage

from loguru import logger

from app.core.config import settings


def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    if not settings.SYSTEM_SMTP_HOST or not settings.SYSTEM_SMTP_USER or not settings.SYSTEM_SMTP_PASSWORD:
        raise RuntimeError("System SMTP is not configured.")

    message = EmailMessage()
    message["From"] = settings.SYSTEM_FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.SYSTEM_SMTP_HOST, settings.SYSTEM_SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings.SYSTEM_SMTP_USER, settings.SYSTEM_SMTP_PASSWORD)
        smtp.send_message(message)


async def send_email(to_email: str, subject: str, body: str) -> None:
    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, body)
        logger.info("System SMTP email sent to {}", to_email)
    except Exception:
        logger.exception("System SMTP email failed for {}", to_email)
        raise
