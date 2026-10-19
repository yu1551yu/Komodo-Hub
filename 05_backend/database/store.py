from __future__ import annotations

import hashlib
import json
from typing import Any

from database.connection import connection

CORE = {
    "users.json": ("users", ["id", "name", "email", "password_hash", "role", "profile", "created_at", "updated_at"]),
    "community_organisations.json": ("organizations", ["id", "name", "region", "status", "created_at", "updated_at"]),
    "community_memberships.json": ("organization_members", ["id", "organization_id", "user_id", "role", "status"]),
    "community_join_requests.json": ("organization_join_requests", ["id", "organization_id", "user_id", "status"]),
    "classes.json": ("classes", ["id", "teacher_id", "name", "access_code"]),
    "enrollments.json": ("class_memberships", ["id", "class_id", "student_id", "joined_at"]),
    "programs.json": ("school_programs", ["id", "teacher_id", "title", "status"]),
    "learning_activities.json": ("program_activities", ["id", "program_id", "title", "status"]),
    "conservation_programs.json": ("conservation_programs", ["id", "title", "status"]),
    "program_enrollments.json": ("program_participation", ["id", "program_id", "user_id", "organization_id", "status"]),
    "community_contributions.json": ("contributions", ["id", "author_id", "organization_id", "title", "type", "status"]),
    "species_sightings.json": ("sighting_reports", ["id", "reporter_id", "species_id", "organization_id", "status"]),
}

KEYS = {
    "password_hash": "passwordHash", "created_at": "createdAt", "updated_at": "updatedAt",
    "organization_id": "organisationId", "user_id": "userId", "teacher_id": "teacherId",
    "access_code": "accessCode", "class_id": "classId", "student_id": "studentId",
    "joined_at": "joinedAt", "program_id": "programId", "author_id": "authorId",
    "reporter_id": "authorId", "species_id": "speciesId",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _row_id(row: dict, index: int) -> str:
    return str(row.get("id") or hashlib.sha256(f"{index}:{_json(row)}".encode()).hexdigest()[:32])


def _value(row: dict, column: str):
    if column == "profile":
        return _json(row.get("studentProfile") or row.get("publicProfile") or row.get("accountProfile") or {})
    return row.get(KEYS.get(column, column))


def read_rows(collection: str) -> list[dict]:
    with connection() as conn:
        cursor = conn.cursor()
        if collection in CORE:
            table, _ = CORE[collection]
            cursor.execute(f"SELECT payload FROM `{table}` ORDER BY id")
        else:
            cursor.execute("SELECT payload FROM app_records WHERE collection_name=%s ORDER BY position_no", (collection,))
        rows = [json.loads(value) if isinstance(value, str) else value for (value,) in cursor.fetchall()]
        cursor.close()
        return rows


def write_rows(collection: str, rows: list[dict]) -> None:
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise TypeError("rows must be a list of objects")
    with connection() as conn:
        cursor = conn.cursor()
        if collection in CORE:
            table, columns = CORE[collection]
            ids = []
            for index, row in enumerate(rows):
                record_id = _row_id(row, index); ids.append(record_id)
                values = []
                for col in columns:
                    value = record_id if col == "id" else _value(row, col)
                    if col == "email" and not value:
                        value = f"{record_id}@legacy.local"
                    if col in {"name", "title", "type", "role", "status"} and value is None:
                        value = ""
                    values.append(value)
                values.append(_json(row))
                names = columns + ["payload"]
                updates = ",".join(f"`{name}`=VALUES(`{name}`)" for name in names if name != "id")
                cursor.execute(
                    f"INSERT INTO `{table}` ({','.join(f'`{name}`' for name in names)}) VALUES ({','.join(['%s'] * len(names))}) "
                    f"ON DUPLICATE KEY UPDATE {updates}", values,
                )
            if ids:
                cursor.execute(f"DELETE FROM `{table}` WHERE id NOT IN ({','.join(['%s'] * len(ids))})", ids)
            else:
                cursor.execute(f"DELETE FROM `{table}`")
            if collection == "users.json":
                cursor.execute("DELETE FROM student_profiles")
                cursor.execute("DELETE FROM teacher_profiles")
                student_rows = [(str(row["id"]), _json(row["studentProfile"])) for row in rows if row.get("id") and isinstance(row.get("studentProfile"), dict)]
                teacher_rows = [(str(row["id"]), _json({"teacherClassIds": row.get("teacherClassIds", [])})) for row in rows if row.get("id") and row.get("role") == "TEACHER"]
                if student_rows:
                    cursor.executemany("INSERT INTO student_profiles(user_id,profile) VALUES(%s,%s)", student_rows)
                if teacher_rows:
                    cursor.executemany("INSERT INTO teacher_profiles(user_id,profile) VALUES(%s,%s)", teacher_rows)
        else:
            cursor.execute("DELETE FROM app_records WHERE collection_name=%s", (collection,))
            cursor.executemany(
                "INSERT INTO app_records(collection_name,record_id,position_no,payload) VALUES(%s,%s,%s,%s)",
                [(collection, _row_id(row, index), index, _json(row)) for index, row in enumerate(rows)],
            )
        conn.commit(); cursor.close()


def read_document(key: str) -> dict:
    with connection() as conn:
        cursor = conn.cursor(); cursor.execute("SELECT payload FROM app_documents WHERE document_key=%s", (key,))
        found = cursor.fetchone(); cursor.close()
        if not found: return {}
        return json.loads(found[0]) if isinstance(found[0], str) else found[0]


def write_document(key: str, value: dict) -> None:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO app_documents(document_key,payload) VALUES(%s,%s) ON DUPLICATE KEY UPDATE payload=VALUES(payload)",
            (key, _json(value)),
        )
        conn.commit(); cursor.close()


def replace_species(rows: list[dict]) -> None:
    with connection() as conn:
        cursor = conn.cursor(); ids = []
        for index, row in enumerate(rows):
            rid = _row_id(row, index); ids.append(rid)
            cursor.execute(
                "INSERT INTO species(id,name,scientific_name,conservation_status,payload) VALUES(%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE name=VALUES(name),scientific_name=VALUES(scientific_name),conservation_status=VALUES(conservation_status),payload=VALUES(payload)",
                (rid, row.get("name") or "Unknown", row.get("latin"), row.get("level"), _json(row)),
            )
        if ids: cursor.execute(f"DELETE FROM species WHERE id NOT IN ({','.join(['%s'] * len(ids))})", ids)
        else: cursor.execute("DELETE FROM species")
        conn.commit(); cursor.close()


def read_species() -> list[dict]:
    with connection() as conn:
        cursor = conn.cursor(); cursor.execute("SELECT payload FROM species ORDER BY name")
        result = [json.loads(v) if isinstance(v, str) else v for (v,) in cursor.fetchall()]; cursor.close(); return result
