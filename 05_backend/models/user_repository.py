from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auth.passwords import hash_password

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_users() -> list[dict[str, Any]]:
    from models.json_store import read_rows
    return read_rows("users.json")


def _write_users(users: list[dict[str, Any]]) -> None:
    from models.json_store import write_rows
    write_rows("users.json", users)


def seed_users_if_empty() -> None:
    if _read_users():
        return
    now = _now_iso()
    demo = [
        {
            "id": "usr_demo_teacher",
            "name": "Bu Sari",
            "email": "teacher@komodo.id",
            "passwordHash": hash_password("demo123"),
            "role": "TEACHER",
            "teacherClassIds": ["c-1"],
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "id": "usr_demo_student",
            "name": "Rafi M.",
            "email": "student@komodo.id",
            "passwordHash": hash_password("demo123"),
            "role": "STUDENT",
            "createdAt": now,
            "updatedAt": now,
        },
    ]
    _write_users(demo)


def seed_public_users_if_missing() -> None:
    users = _read_users()
    now = _now_iso()
    demos = [
        {
            "id": "usr_demo_public",
            "name": "Maya S.",
            "email": "public@komodo.id",
            "passwordHash": hash_password("demo123"),
            "role": "PUBLIC",
            "publicProfile": {"location": "Bali", "interestSpecies": ["Bali Starling"]},
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "id": "usr_demo_community_admin",
            "name": "Dewi L.",
            "email": "community@komodo.id",
            "passwordHash": hash_password("demo123"),
            "role": "PUBLIC",
            "publicProfile": {"location": "Labuan Bajo", "interestSpecies": ["Komodo dragon"]},
            "createdAt": now,
            "updatedAt": now,
        },
    ]
    changed = False
    existing_emails = {str(user.get("email", "")).lower() for user in users}
    existing_ids = {user.get("id") for user in users}
    for demo in demos:
        if demo["email"] not in existing_emails and demo["id"] not in existing_ids:
            users.append(demo)
            changed = True
    if changed:
        _write_users(users)


def seed_admin_user_if_missing() -> None:
    users = _read_users()
    if any(str(user.get("email", "")).lower() == "admin@komodo.id" for user in users):
        return
    now = _now_iso()
    users.append(
        {
            "id": "usr_demo_admin",
            "name": "Anisa K.",
            "email": "admin@komodo.id",
            "passwordHash": hash_password("demo123"),
            "role": "ADMIN",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    _write_users(users)


def find_by_email(email: str) -> dict[str, Any] | None:
    key = email.strip().lower()
    for u in _read_users():
        if str(u.get("email", "")).lower() == key:
            return u
    return None


def find_by_id(user_id: str) -> dict[str, Any] | None:
    for u in _read_users():
        if u.get("id") == user_id:
            return u
    return None


def search_users(query: str, limit: int = 20) -> list[dict[str, Any]]:
    term = str(query or "").strip().lower()
    if len(term) < 2:
        return []
    matches = []
    for user in _read_users():
        if user.get("role") == "ADMIN":
            continue
        haystack = f"{user.get('name', '')} {user.get('email', '')}".lower()
        if term in haystack:
            matches.append(user)
    return matches[:limit]


def create_user(
    name: str,
    email: str,
    password: str,
    role: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    users = _read_users()
    if any(str(u.get("email", "")).lower() == email.lower() for u in users):
        raise ValueError("EMAIL_EXISTS")
    now = _now_iso()
    user = {
        "id": f"usr_{secrets.token_hex(8)}",
        "name": name,
        "email": email.lower(),
        "passwordHash": hash_password(password),
        "role": role,
        "createdAt": now,
        "updatedAt": now,
    }
    if extra:
        user.update(extra)
    users.append(user)
    _write_users(users)
    return user


def delete_user(user_id: str) -> bool:
    users = _read_users()
    next_users = [u for u in users if u.get("id") != user_id]
    if len(next_users) == len(users):
        return False
    _write_users(next_users)
    return True


def update_user(user_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    users = _read_users()
    for i, u in enumerate(users):
        if u.get("id") == user_id:
            u = {**u, **patch, "updatedAt": _now_iso()}
            users[i] = u
            _write_users(users)
            return u
    return None


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "createdAt": user.get("createdAt"),
        "updatedAt": user.get("updatedAt"),
    }
