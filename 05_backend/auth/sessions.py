from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSIONS_FILE = ROOT / "data" / "sessions.json"
SESSION_DAYS = 14
COOKIE_NAME = "komodo_session"


def _load() -> dict[str, dict]:
    raise RuntimeError("Bulk session loading is not supported")


def _save(sessions: dict[str, dict]) -> None:
    raise RuntimeError("Bulk session saving is not supported")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    from database.connection import connection
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(%s,%s,%s)", (_token_hash(token), user_id, expires))
        conn.commit(); cursor.close()
    return token


def delete_session(token: str) -> None:
    from database.connection import connection
    with connection() as conn:
        cursor = conn.cursor(); cursor.execute("DELETE FROM sessions WHERE token_hash=%s", (_token_hash(token),))
        conn.commit(); cursor.close()


def get_user_id_for_token(token: str | None) -> str | None:
    if not token:
        return None
    from database.connection import connection
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT user_id AS userId, expires_at AS expiresAt FROM sessions WHERE token_hash=%s", (_token_hash(token),))
        row = cursor.fetchone(); cursor.close()
    if not row:
        return None
    try:
        expires = datetime.fromisoformat(row["expiresAt"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            delete_session(token)
            return None
    except (KeyError, ValueError):
        delete_session(token)
        return None
    return row.get("userId")
