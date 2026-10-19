from __future__ import annotations

from models.json_store import DATA_DIR, read_rows, write_rows
from models.work_repository import create_row, update_row

PROGRAMS = "conservation_programs.json"
ENROLLMENTS = "program_enrollments.json"
APPLICATIONS = "program_join_requests.json"


def seed_conservation_programs_if_empty() -> None:
    if not read_rows(PROGRAMS):
        write_rows(
            PROGRAMS,
            [
                {
                    "id": "cp_reef_watch",
                    "title": "Reef Watch Citizen Survey",
                    "summary": "Community volunteers record coastal wildlife signs and reef health observations.",
                    "description": "A public conservation program for safe shoreline observation, photo evidence and community reporting around Labuan Bajo.",
                    "participationInfo": "Open to individual public users and approved community organisations.",
                    "status": "published",
                    "allowedParticipantTypes": ["individual", "community"],
                    "region": "East Nusa Tenggara",
                    "media": {"type": "emoji", "value": "RW"},
                    "createdAt": "2026-10-01T00:00:00+00:00",
                    "updatedAt": "2026-10-01T00:00:00+00:00",
                },
                {
                    "id": "cp_starling_guard",
                    "title": "Bali Starling Habitat Guard",
                    "summary": "Support habitat awareness and responsible observation for Bali starling recovery.",
                    "description": "Participants help share verified habitat knowledge and take part in low-impact conservation education activities.",
                    "participationInfo": "Open to individual public users.",
                    "status": "published",
                    "allowedParticipantTypes": ["individual"],
                    "region": "Bali",
                    "media": {"type": "emoji", "value": "BS"},
                    "createdAt": "2026-10-01T00:00:00+00:00",
                    "updatedAt": "2026-10-01T00:00:00+00:00",
                },
            ],
        )
    if not read_rows(ENROLLMENTS):
        write_rows(ENROLLMENTS, [])
    if not read_rows(APPLICATIONS):
        write_rows(APPLICATIONS, [])


def list_programs() -> list[dict]:
    seed_conservation_programs_if_empty()
    return [row for row in read_rows(PROGRAMS) if row.get("status") == "published"]


def find_program(program_id: str) -> dict | None:
    key = str(program_id or "").strip()
    if not key or "/" in key or "\\" in key:
        raise ValueError("INVALID_ID")
    return next((row for row in list_programs() if row.get("id") == key), None)


def list_enrollments() -> list[dict]:
    seed_conservation_programs_if_empty()
    return read_rows(ENROLLMENTS)


def enrollments_for_user(user_id: str) -> list[dict]:
    programs = {row["id"]: row for row in list_programs()}
    return [
        {**row, "program": programs.get(row.get("programId"))}
        for row in list_enrollments()
        if row.get("userId") == user_id and row.get("programId") in programs
    ]


def enrollments_for_organisation(organisation_id: str) -> list[dict]:
    programs = {row["id"]: row for row in list_programs()}
    return [
        {**row, "program": programs.get(row.get("programId"))}
        for row in list_enrollments()
        if row.get("organisationId") == organisation_id and row.get("programId") in programs
    ]


def enrollments_for_program(program_id: str) -> list[dict]:
    return [row for row in list_enrollments() if row.get("programId") == program_id]


def create_enrollment(values: dict) -> tuple[dict, bool]:
    existing = next(
        (
            row
            for row in list_enrollments()
            if row.get("programId") == values.get("programId")
            and row.get("userId") == values.get("userId")
            and row.get("organisationId") == values.get("organisationId")
        ),
        None,
    )
    if existing:
        return existing, False
    return create_row(ENROLLMENTS, "penr", values), True


def list_program_applications() -> list[dict]:
    seed_conservation_programs_if_empty()
    return read_rows(APPLICATIONS)


def applications_for_user(user_id: str) -> list[dict]:
    return [row for row in list_program_applications() if row.get("userId") == user_id]


def applications_for_organisation(organisation_id: str) -> list[dict]:
    return [row for row in list_program_applications() if row.get("organisationId") == organisation_id]


def find_program_application(application_id: str) -> dict | None:
    return next((row for row in list_program_applications() if row.get("id") == application_id), None)


def create_program_application(values: dict) -> tuple[dict, bool]:
    existing = next((row for row in list_program_applications() if row.get("programId") == values.get("programId") and row.get("userId") == values.get("userId") and row.get("organisationId") == values.get("organisationId") and row.get("status") == "pending"), None)
    if existing:
        return existing, False
    return create_row(APPLICATIONS, "preq", values), True


def update_program_application(application_id: str, values: dict) -> dict | None:
    return update_row(APPLICATIONS, application_id, values, {"status", "note", "reviewedBy", "reviewedAt", "updatedAt"})


def create_program(values: dict) -> dict:
    return create_row(PROGRAMS, "cp", values)


def update_program(program_id: str, values: dict) -> dict | None:
    return update_row(PROGRAMS, program_id, values, {"title", "summary", "description", "participationInfo", "region", "conservationGoal", "status", "allowedParticipantTypes", "organisationId", "updatedAt"})
