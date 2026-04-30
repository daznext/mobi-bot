from __future__ import annotations

import sqlite3
from pathlib import Path


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    kindle_email TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get_kindle_email(self, user_id: int) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT kindle_email FROM user_settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row[0] if row else None

    def set_kindle_email(self, user_id: int, email: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_settings (user_id, kindle_email, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    kindle_email = excluded.kindle_email,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, email),
            )

    def delete_kindle_email(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))

