from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from pathlib import Path

from .config import Config


class MailError(RuntimeError):
    pass


async def send_to_kindle(config: Config, kindle_email: str, attachment: Path) -> None:
    if not config.smtp_configured:
        raise MailError("SMTP is not configured.")

    await asyncio.to_thread(_send_to_kindle_sync, config, kindle_email, attachment)


def _send_to_kindle_sync(config: Config, kindle_email: str, attachment: Path) -> None:
    message = EmailMessage()
    message["From"] = config.smtp_from
    message["To"] = kindle_email
    message["Subject"] = "Converted book"
    message.set_content("Converted MOBI file is attached.")

    message.add_attachment(
        attachment.read_bytes(),
        maintype="application",
        subtype="x-mobipocket-ebook",
        filename=attachment.name,
    )

    try:
        if config.smtp_use_ssl:
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                _login_if_needed(smtp, config)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                smtp.ehlo()
                if config.smtp_use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                _login_if_needed(smtp, config)
                smtp.send_message(message)
    except OSError as exc:
        raise MailError(f"SMTP connection failed: {exc}") from exc
    except smtplib.SMTPException as exc:
        raise MailError(f"SMTP send failed: {exc}") from exc


def _login_if_needed(smtp: smtplib.SMTP, config: Config) -> None:
    if config.smtp_username and config.smtp_password:
        smtp.login(config.smtp_username, config.smtp_password)

