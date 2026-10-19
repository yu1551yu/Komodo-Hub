from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CLASSES_FILE = DATA_DIR / "classes.json"
APP_DATA = DATA_DIR / "komodo_hub.json"

LEGACY_TEACHER_MAP = {"u-teacher": "usr_demo_teacher"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read() -> list[dict[str, Any]]:
    from models.json_store import read_rows
    return read_rows("classes.json")


def _write(classes: list[dict[str, Any]]) -> None:
    from models.json_store import write_rows
    write_rows("classes.json", classes)


def _normalize_code(code: str) -> str:
    return re.sub(r"\s+", "", str(code or "").strip().upper())


def public_class(cls: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": cls["id"],
        "name": cls["name"],
        "description": cls.get("description", ""),
        "grade": cls.get("grade", ""),
        "teacherId": cls["teacherId"],
        "accessCode": cls.get("accessCode"),
        "createdAt": cls.get("createdAt"),
        "updatedAt": cls.get("updatedAt"),
    }


def seed_classes_if_empty() -> None:
    if _read():
        return
    now = _now_iso()
    classes: list[dict[str, Any]] = []
    from database.store import read_document
    app = read_document("komodo_hub")
    if app:
        for raw in app.get("classes") or []:
            tid = LEGACY_TEACHER_MAP.get(raw.get("teacherId"), raw.get("teacherId"))
            classes.append(
                {
                    "id": raw["id"],
                    "name": raw.get("name", "Class"),
                    "teacherId": tid,
                    "accessCode": _normalize_code(raw.get("accessCode", "")),
                    "accessCodeExpiresAt": raw.get("accessCodeExpiresAt"),
                    "createdAt": now,
                    "updatedAt": now,
                }
            )
    if not classes:
        classes.append(
            {
                "id": "c-1",
                "name": "Grade 5 Biology Conservation Class",
                "teacherId": "usr_demo_teacher",
                "accessCode": "UJUNG-5A-2026",
                "accessCodeExpiresAt": None,
                "createdAt": now,
                "updatedAt": now,
            }
        )
    _ensure_unique_access_codes(classes)
    _write(classes)


def _ensure_unique_access_codes(classes: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for cls in classes:
        code = _normalize_code(cls.get("accessCode", ""))
        if not code or code in seen:
            cls["accessCode"] = f"KOMODO-{secrets.token_hex(3).upper()}"
            code = cls["accessCode"]
        seen.add(code)
        cls["accessCode"] = code


def find_by_id(class_id: str) -> dict[str, Any] | None:
    return next((c for c in _read() if c.get("id") == class_id), None)


def find_by_access_code(code: str) -> dict[str, Any] | None:
    key = _normalize_code(code)
    if not key:
        return None
    return next((c for c in _read() if _normalize_code(c.get("accessCode")) == key), None)


def list_by_teacher(teacher_id: str) -> list[dict[str, Any]]:
    return [public_class(c) for c in _read() if c.get("teacherId") == teacher_id]


def _new_unique_access_code(classes: list[dict[str, Any]] | None = None) -> str:
    rows = classes if classes is not None else _read()
    seen = {_normalize_code(c.get("accessCode")) for c in rows}
    for _ in range(64):
        code = f"KOMODO-{secrets.token_hex(3).upper()}"
        if code not in seen:
            return code
    raise ValueError("CODE_GEN_FAILED")


def create_class(teacher_id: str, name: str, description: str = "", grade: str = "") -> dict[str, Any]:
    clean_name = str(name or "").strip()
    if len(clean_name) < 2:
        raise ValueError("INVALID_NAME")
    classes = _read()
    now = _now_iso()
    row: dict[str, Any] = {
        "id": f"cls_{secrets.token_hex(6)}",
        "name": clean_name,
        "description": str(description or "").strip(),
        "grade": str(grade or "").strip(),
        "teacherId": teacher_id,
        "accessCode": _new_unique_access_code(classes),
        "accessCodeExpiresAt": None,
        "createdAt": now,
        "updatedAt": now,
    }
    classes.append(row)
    _write(classes)
    return row


def update_class(class_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    classes = _read()
    for index, row in enumerate(classes):
        if row.get("id") != class_id:
            continue
        allowed = {key: str(value or "").strip() for key, value in patch.items() if key in {"name", "description", "grade"}}
        classes[index] = {**row, **allowed, "updatedAt": _now_iso()}
        _write(classes)
        return classes[index]
    return None


def regenerate_access_code(teacher_id: str, class_id: str) -> dict[str, Any] | None:
    classes = _read()
    for i, cls in enumerate(classes):
        if cls.get("id") != class_id:
            continue
        if cls.get("teacherId") != teacher_id:
            raise ValueError("FORBIDDEN")
        classes[i] = {
            **cls,
            "accessCode": _new_unique_access_code(classes),
            "updatedAt": _now_iso(),
        }
        _write(classes)
        return classes[i]
    return None


def is_access_code_valid(cls: dict[str, Any]) -> bool:
    expires = cls.get("accessCodeExpiresAt")
    if not expires:
        return True
    try:
        exp = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) <= exp
    except ValueError:
        return False
