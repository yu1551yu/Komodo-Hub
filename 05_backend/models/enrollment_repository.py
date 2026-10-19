from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ENROLLMENTS_FILE = DATA_DIR / "enrollments.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read() -> list[dict[str, Any]]:
    from models.json_store import read_rows
    return read_rows("enrollments.json")


def _write(rows: list[dict[str, Any]]) -> None:
    from models.json_store import write_rows
    write_rows("enrollments.json", rows)


def seed_enrollments_if_empty() -> None:
    if _read():
        return
    now = _now_iso()
    _write(
        [
            {
                "id": "enr_demo_1",
                "studentId": "usr_demo_student",
                "classId": "c-1",
                "joinedAt": now,
            }
        ]
    )


def find_enrollment(student_id: str, class_id: str) -> dict[str, Any] | None:
    return next(
        (
            e
            for e in _read()
            if e.get("studentId") == student_id and e.get("classId") == class_id
        ),
        None,
    )


def list_for_student(student_id: str) -> list[dict[str, Any]]:
    return [e for e in _read() if e.get("studentId") == student_id]


def list_student_ids_for_class(class_id: str) -> list[str]:
    return [e["studentId"] for e in _read() if e.get("classId") == class_id]


def list_student_ids_for_teacher(teacher_id: str, class_ids: list[str]) -> list[str]:
    cid_set = set(class_ids)
    return [
        e["studentId"]
        for e in _read()
        if e.get("classId") in cid_set
    ]


def create_enrollment(student_id: str, class_id: str) -> dict[str, Any]:
    if find_enrollment(student_id, class_id):
        raise ValueError("ALREADY_ENROLLED")
    row = {
        "id": f"enr_{secrets.token_hex(8)}",
        "studentId": student_id,
        "classId": class_id,
        "joinedAt": _now_iso(),
    }
    rows = _read()
    rows.append(row)
    _write(rows)
    return row


def remove_enrollment(student_id: str, class_id: str) -> bool:
    rows = _read()
    next_rows = [row for row in rows if not (row.get("studentId") == student_id and row.get("classId") == class_id)]
    if len(next_rows) == len(rows):
        return False
    _write(next_rows)
    return True
