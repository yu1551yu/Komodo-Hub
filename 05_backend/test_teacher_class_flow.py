"""Teacher creates class on server; student registers with that access code."""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from auth.handlers import handle_login, handle_register
from models.user_repository import find_by_email
from auth.sessions import COOKIE_NAME
from models.class_repository import seed_classes_if_empty
from models.enrollment_repository import seed_enrollments_if_empty
from models.user_repository import seed_users_if_empty
from routes.teacher import handle_create_class, handle_regenerate_access_code


class MockHandler:
    def __init__(self, cookie: str | None = None):
        self.headers = {}
        if cookie:
            self.headers["Cookie"] = f"{COOKIE_NAME}={cookie}"


def main() -> None:
    seed_users_if_empty()
    seed_classes_if_empty()
    seed_enrollments_if_empty()

    tag = secrets.token_hex(4)
    teacher_email = f"teacher.flow.{tag}@komodo.id"
    student_email = f"student.flow.{tag}@komodo.id"

    s, body = handle_register(
        {
            "name": "Flow Teacher",
            "email": teacher_email,
            "password": "demo123",
            "role": "TEACHER",
        }
    )
    assert s == 201, (s, body)

    s, _, token = handle_login({"email": teacher_email, "password": "demo123"})
    assert s == 200 and token, (s, body)

    s, payload = handle_create_class(MockHandler(token), {"name": "Flow Class 5A"})
    assert s == 201, (s, payload)
    access_code = payload["data"]["class"]["accessCode"]
    class_id = payload["data"]["class"]["id"]
    assert access_code, payload

    s, regen = handle_regenerate_access_code(MockHandler(token), class_id)
    assert s == 200, (s, regen)
    assert regen["data"]["class"]["accessCode"] != access_code

    s, reg_body = handle_register(
        {
            "name": "Flow Student",
            "email": student_email,
            "password": "demo123",
            "role": "STUDENT",
            "accessCode": regen["data"]["class"]["accessCode"],
        }
    )
    assert s == 201, (s, reg_body)

    bad_email = f"student.bad.{tag}@komodo.id"
    s, bad_body = handle_register(
        {
            "name": "Bad Code Student",
            "email": bad_email,
            "password": "demo123",
            "role": "STUDENT",
            "accessCode": "NOT-A-VALID-CODE",
        }
    )
    assert s == 404, (s, bad_body)
    assert find_by_email(bad_email) is None

    print("teacher class flow tests passed")


if __name__ == "__main__":
    main()
