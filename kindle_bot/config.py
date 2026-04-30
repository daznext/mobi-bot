from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    ebook_convert_bin: str
    db_path: Path
    output_dir: Path
    mail_backend: str
    smtp_host: str
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_from: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    gmail_credentials_path: Path
    gmail_token_path: Path

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

        smtp_host = os.getenv("SMTP_HOST", "")
        smtp_from = os.getenv("SMTP_FROM") or os.getenv("SMTP_USERNAME", "")

        return cls(
            telegram_bot_token=token,
            ebook_convert_bin=os.getenv("EBOOK_CONVERT_BIN", "ebook-convert"),
            db_path=Path(os.getenv("BOT_DB_PATH", "./data/bot.sqlite3")),
            output_dir=Path(os.getenv("BOT_OUTPUT_DIR", "./data/output")),
            mail_backend=os.getenv("MAIL_BACKEND", "smtp").strip().lower(),
            smtp_host=smtp_host,
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            smtp_from=smtp_from,
            smtp_use_tls=_as_bool(os.getenv("SMTP_USE_TLS"), True),
            smtp_use_ssl=_as_bool(os.getenv("SMTP_USE_SSL"), False),
            gmail_credentials_path=Path(os.getenv("GMAIL_CREDENTIALS_PATH", "./secrets/gmail_credentials.json")),
            gmail_token_path=Path(os.getenv("GMAIL_TOKEN_PATH", "./secrets/gmail_token.json")),
        )

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def gmail_api_configured(self) -> bool:
        return bool(self.smtp_from and self.gmail_token_path.exists())
