from __future__ import annotations

import asyncio
from email.message import EmailMessage
from socket import gaierror, timeout as socket_timeout
import ssl

import smtplib
from loguru import logger

from app.core.config import settings
from app.services.email.templates import EmailContent

TRANSIENT_SMTP_ERRORS = (
    smtplib.SMTPConnectError,
    smtplib.SMTPServerDisconnected,
    smtplib.SMTPHeloError,
    smtplib.SMTPDataError,
    TimeoutError,
    socket_timeout,
    gaierror,
)


def _mask_email(email: str) -> str:
    local_part, _, domain = email.partition("@")
    if not domain:
        return "***"
    if len(local_part) <= 2:
        masked_local_part = "*" * len(local_part)
    else:
        masked_local_part = f"{local_part[0]}***{local_part[-1]}"
    return f"{masked_local_part}@{domain}"


class MailService:
    @property
    def enabled(self) -> bool:
        return settings.email_enabled

    async def verify_connection(self) -> bool:
        if not self.enabled:
            logger.warning(
                "SMTP is not configured. Email delivery is disabled until SYSTEM_SMTP_* and SYSTEM_FROM_EMAIL are set."
            )
            return False

        # Gmail App Password auth requires Google 2FA to be enabled on the
        # account. Generate the 16-character password from:
        # Google Account -> Security -> 2-Step Verification -> App Passwords.
        await asyncio.to_thread(self._verify_connection_sync)
        logger.info("SMTP connection verified for {}", settings.SYSTEM_SMTP_HOST)
        if settings.SYSTEM_FROM_EMAIL.lower() != settings.SYSTEM_SMTP_USER.lower():
            logger.warning(
                "SYSTEM_FROM_EMAIL ({}) differs from SYSTEM_SMTP_USER ({}). Gmail may rewrite the From header.",
                settings.SYSTEM_FROM_EMAIL,
                settings.SYSTEM_SMTP_USER,
            )
        return True

    def _verify_connection_sync(self) -> None:
        tls_context = ssl.create_default_context()
        with smtplib.SMTP(settings.SYSTEM_SMTP_HOST, settings.SYSTEM_SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=tls_context)
            smtp.ehlo()
            smtp.login(settings.SYSTEM_SMTP_USER, settings.SYSTEM_SMTP_PASSWORD)

    async def send(self, *, to_email: str, content: EmailContent, reply_to: str | None = None) -> None:
        if not self.enabled:
            raise RuntimeError("SMTP is not configured.")

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                await asyncio.to_thread(self._send_sync, to_email, content, reply_to)
                logger.info(
                    "Email sent to {} with subject {} on attempt {}",
                    _mask_email(to_email),
                    content.subject,
                    attempt,
                )
                return
            except TRANSIENT_SMTP_ERRORS as exc:
                last_error = exc
                logger.warning(
                    "Transient email delivery error for {} on attempt {}: {}",
                    _mask_email(to_email),
                    attempt,
                    exc,
                )
                if attempt < 3:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "Permanent email delivery error for {} with subject {}",
                    _mask_email(to_email),
                    content.subject,
                )
                raise

        if last_error is not None:
            raise last_error

    def _send_sync(self, to_email: str, content: EmailContent, reply_to: str | None) -> None:
        tls_context = ssl.create_default_context()
        message = EmailMessage()
        message["From"] = settings.SYSTEM_FROM_EMAIL
        message["To"] = to_email
        message["Subject"] = content.subject
        if reply_to:
            message["Reply-To"] = reply_to
        message.set_content(content.text)
        message.add_alternative(content.html, subtype="html")

        with smtplib.SMTP(settings.SYSTEM_SMTP_HOST, settings.SYSTEM_SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=tls_context)
            smtp.ehlo()
            smtp.login(settings.SYSTEM_SMTP_USER, settings.SYSTEM_SMTP_PASSWORD)
            smtp.send_message(message)


mail_service = MailService()
