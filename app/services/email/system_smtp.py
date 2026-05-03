import asyncio
import smtplib
from email.message import EmailMessage

from loguru import logger

from app.core.config import settings


def _send_email_sync(to_email: str, subject: str, body_html: str) -> None:
    if not settings.SYSTEM_SMTP_HOST or not settings.SYSTEM_SMTP_USER or not settings.SYSTEM_SMTP_PASSWORD:
        raise RuntimeError("System SMTP is not configured.")

    message = EmailMessage()
    message["From"] = settings.SYSTEM_FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("This email requires an HTML-capable client.")
    message.add_alternative(body_html, subtype="html")

    with smtplib.SMTP(settings.SYSTEM_SMTP_HOST, settings.SYSTEM_SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings.SYSTEM_SMTP_USER, settings.SYSTEM_SMTP_PASSWORD)
        smtp.send_message(message)


async def send_email(to: str, subject: str, body_html: str) -> None:
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _send_email_sync, to, subject, body_html)
        logger.info("System SMTP email sent to {}", to)
    except Exception:
        logger.exception("System SMTP email failed for {}", to)
        raise
