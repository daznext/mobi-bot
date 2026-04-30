from __future__ import annotations

import asyncio
import base64
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path

from .config import Config


class MailError(RuntimeError):
    pass


async def send_to_kindle(config: Config, kindle_email: str, attachment: Path) -> None:
    if config.mail_backend == "smtp":
        if not config.smtp_configured:
            raise MailError("SMTP is not configured.")
        await asyncio.to_thread(_send_to_kindle_smtp_sync, config, kindle_email, attachment)
        return

    if config.mail_backend == "gmail_api":
        if not config.gmail_api_configured:
            raise MailError("Gmail API is not configured. Check SMTP_FROM and GMAIL_TOKEN_PATH.")
        await asyncio.to_thread(_send_to_kindle_gmail_api_sync, config, kindle_email, attachment)
        return

    raise MailError(f"Unsupported MAIL_BACKEND: {config.mail_backend}")


def _build_message(config: Config, kindle_email: str, attachment: Path) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config.smtp_from
    message["To"] = kindle_email
    message["Subject"] = "Converted book"
    message.set_content("Converted book file is attached.")

    content_type = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
    maintype, subtype = content_type.split("/", 1)
    message.add_attachment(
        attachment.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=attachment.name,
    )
    return message


def _send_to_kindle_smtp_sync(config: Config, kindle_email: str, attachment: Path) -> None:
    message = _build_message(config, kindle_email, attachment)
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


def _send_to_kindle_gmail_api_sync(config: Config, kindle_email: str, attachment: Path) -> None:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError as exc:
        raise MailError("Gmail API dependencies are not installed. Run pip install -r requirements.txt.") from exc

    try:
        creds = Credentials.from_authorized_user_file(
            str(config.gmail_token_path),
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            config.gmail_token_path.write_text(creds.to_json(), encoding="utf-8")

        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        message = _build_message(config, kindle_email, attachment)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except OSError as exc:
        raise MailError(f"Gmail token read/write failed: {exc}") from exc
    except HttpError as exc:
        raise MailError(f"Gmail API send failed: {exc}") from exc
