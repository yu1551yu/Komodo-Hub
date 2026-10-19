from __future__ import annotations

from typing import Any


def error_body(code: str, message: str, details: Any = None) -> dict:
    body = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def success_body(data: dict | None = None) -> dict:
    out = {"ok": True}
    if data:
        out["data"] = data
    return out
