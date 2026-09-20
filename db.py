"""SQLite persistence for accounts, portfolios and the activity log.

The database path can be overridden with the UUB_DB_PATH environment variable.
NOTE: on Streamlit Community Cloud the local disk is ephemeral - data is lost
when the app restarts or is redeployed. For a real deployment point this layer
at a hosted database (Postgres / Supabase / Neon) instead.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

DB_PATH = os.environ.get("UUB_DB_PATH", os.path.join("data", "uub.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portfolios (
                user_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ts TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'info'
            );
            CREATE INDEX IF NOT EXISTS idx_activity_user ON activity(user_id, id DESC);
            """
        )


# ---------------------------------------------------------------- users
def create_user(full_name: str, email: str, password_hash: str, salt: str) -> Optional[int]:
    try:
        with get_conn() as c:
            cur = c.execute(
                "INSERT INTO users (full_name, email, password_hash, salt, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (full_name, email, password_hash, salt, _now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def set_login_state(user_id: int, failed_attempts: int, locked_until: Optional[str]) -> None:
    with get_conn() as c:
        c.execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
            (failed_attempts, locked_until, user_id),
        )


def update_password(user_id: int, password_hash: str, salt: str) -> None:
    with get_conn() as c:
        c.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (password_hash, salt, user_id),
        )


# ------------------------------------------------------------ portfolios
def load_portfolio(user_id: int) -> Optional[dict[str, Any]]:
    with get_conn() as c:
        row = c.execute("SELECT state_json FROM portfolios WHERE user_id = ?", (user_id,)).fetchone()
    return json.loads(row["state_json"]) if row else None


def save_portfolio(user_id: int, state: dict[str, Any]) -> None:
    with get_conn() as c:
        c.execute(
            "INSERT INTO portfolios (user_id, state_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET state_json = excluded.state_json, "
            "updated_at = excluded.updated_at",
            (user_id, json.dumps(state), _now()),
        )


# -------------------------------------------------------------- activity
def log_activity(user_id: int, actor: str, action: str, detail: str, level: str = "info") -> None:
    with get_conn() as c:
        c.execute(
            "INSERT INTO activity (user_id, ts, actor, action, detail, level) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, _now(), actor, action, detail, level),
        )


def get_activity(user_id: int, limit: int = 300) -> list[dict[str, Any]]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT ts, actor, action, detail, level FROM activity "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
