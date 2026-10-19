from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Callable

from api.errors import error_body
from auth.sessions import COOKIE_NAME, get_user_id_for_token
from models.user_repository import find_by_id, public_user


def parse_session_token(handler) -> str | None:
    cookie_header = handler.headers.get("Cookie")
    if not cookie_header:
        return None
    jar = SimpleCookie()
    jar.load(cookie_header)
    morsel = jar.get(COOKIE_NAME)
    return morsel.value if morsel else None


def get_current_user(handler) -> dict | None:
    token = parse_session_token(handler)
    user_id = get_user_id_for_token(token)
    if not user_id:
        return None
    user = find_by_id(user_id)
    return public_user(user) if user else None


def require_auth(handler) -> tuple[dict | None, dict | None]:
    user = get_current_user(handler)
    if not user:
        return None, error_body("UNAUTHORIZED", "Authentication required.")
    return user, None


def require_role(handler, *roles: str) -> tuple[dict | None, dict | None]:
    user, err = require_auth(handler)
    if err:
        return None, err
    if user["role"] not in roles:
        return None, error_body("FORBIDDEN", "You do not have permission for this resource.")
    return user, None


def set_session_cookie(handler, token: str) -> None:
    handler.send_header(
        "Set-Cookie",
        f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={14 * 24 * 3600}",
    )


def clear_session_cookie(handler) -> None:
    handler.send_header(
        "Set-Cookie",
        f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
    )
