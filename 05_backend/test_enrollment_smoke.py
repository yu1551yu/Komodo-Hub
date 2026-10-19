"""Smoke tests for class enrollment (join by access code)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from auth.handlers import handle_login
from auth.sessions import COOKIE_NAME
from models.class_repository import seed_classes_if_empty
from models.enrollment_repository import seed_enrollments_if_empty
from models.user_repository import create_user, seed_users_if_empty
from routes.classes import handle_join_class
from routes.student import handle_my_classes


class MockHandler:
    def __init__(self, cookie: str | None = None):
        self.headers = {}
        if cookie:
            self.headers["Cookie"] = f"{COOKIE_NAME}={cookie}"


def _login(email: str, password: str = "demo123") -> str:
    status, body, token = handle_login({"email": email, "password": password})
    assert status == 200 and token, (status, body)
    return token


def main() -> None:
    seed_users_if_empty()
    seed_classes_if_empty()
    seed_enrollments_if_empty()

    # Unauthenticated join -> 401
    status, payload = handle_join_class(MockHandler(), {"accessCode": "UJUNG-5A-2026"})
    assert status == 401, (status, payload)
    assert payload["error"]["code"] == "UNAUTHORIZED"

    # Teacher cannot join -> 403
    teacher_token = _login("teacher@komodo.id")
    status, payload = handle_join_class(
        MockHandler(teacher_token), {"accessCode": "UJUNG-5A-2026"}
    )
    assert status == 403, (status, payload)
    assert payload["error"]["code"] == "FORBIDDEN"

    # Invalid access code -> 404
    student_token = _login("student@komodo.id")
    status, payload = handle_join_class(
        MockHandler(student_token), {"accessCode": "NOT-A-REAL-CODE"}
    )
    assert status == 404, (status, payload)
    assert payload["error"]["code"] == "INVALID_ACCESS_CODE"

    # Reject classId in body -> 400
    status, payload = handle_join_class(
        MockHandler(student_token), {"accessCode": "UJUNG-5A-2026", "classId": "c-1"}
    )
    assert status == 400, (status, payload)

    # Duplicate join -> 409
    status, payload = handle_join_class(
        MockHandler(student_token), {"accessCode": "UJUNG-5A-2026"}
    )
    assert status == 409, (status, payload)
    assert payload["error"]["code"] == "ALREADY_ENROLLED"

    # Demo student already enrolled — list classes
    status, payload = handle_my_classes(MockHandler(student_token))
    assert status == 200, (status, payload)
    assert len(payload["data"]["classes"]) >= 1

    # New student + valid access code -> 200
    new_student = create_user(
        "Join Test",
        f"join.test.{__import__('secrets').token_hex(4)}@komodo.id",
        "demo123",
        "STUDENT",
    )
    new_token = _login(new_student["email"])
    status, payload = handle_join_class(
        MockHandler(new_token), {"accessCode": "UJUNG-5A-2026"}
    )
    assert status == 200, (status, payload)
    assert payload["data"]["class"]["id"] == "c-1"
    assert payload["data"]["enrollment"]["studentId"] == new_student["id"]

    print("enrollment smoke tests passed")


if __name__ == "__main__":
    main()
