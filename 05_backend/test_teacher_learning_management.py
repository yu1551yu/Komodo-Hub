from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from auth.handlers import handle_login
from models.class_repository import create_class
from models.enrollment_repository import create_enrollment
from models.user_repository import create_user
from routes.student_learning import get_my_program
from routes.teacher import handle_get_class, handle_patch_class, handle_remove_student
from routes.teacher_learning import (
    activity_status, get_program, material_status, patch_program, post_activity,
    post_material, post_program, program_classes, program_status,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
FILES = ["users.json", "classes.json", "enrollments.json", "sessions.json", "programs.json", "program_classes.json", "materials.json", "learning_activities.json"]


class MockHandler:
    def __init__(self, token: str):
        self.headers = {"Cookie": f"komodo_session={token}"}


def login(email: str, password: str) -> MockHandler:
    status, _, token = handle_login({"email": email, "password": password})
    assert status == 200 and token
    return MockHandler(token)


def main():
    backup_dir = Path(tempfile.mkdtemp(prefix="komodo-management-test-"))
    existed = set()
    try:
        for filename in FILES:
            source = DATA_DIR / filename
            if source.exists():
                shutil.copy2(source, backup_dir / filename); existed.add(filename)

        teacher_a = create_user("Owner A", "owner.a@test.local", "demo123", "TEACHER")
        teacher_b = create_user("Owner B", "owner.b@test.local", "demo123", "TEACHER")
        student = create_user("Learner", "learner@test.local", "demo123", "STUDENT")
        class_a = create_class(teacher_a["id"], "Owner A Class")
        class_b = create_class(teacher_b["id"], "Owner B Class")
        create_enrollment(student["id"], class_a["id"])

        handler_a = login("owner.a@test.local", "demo123")
        handler_b = login("owner.b@test.local", "demo123")
        handler_student = login("learner@test.local", "demo123")

        assert handle_get_class(handler_a, class_a["id"])[0] == 200
        assert handle_get_class(handler_b, class_a["id"])[0] == 403
        assert handle_get_class(handler_student, class_a["id"])[0] == 403
        assert handle_patch_class(handler_a, class_a["id"], {"grade": "6", "description": "Field biology"})[0] == 200

        status, payload = post_program(handler_a, {"title": "Forest Guardians", "description": "Forest study", "learningObjectives": "Identify threats", "classIds": [class_a["id"]]})
        assert status == 201
        program_id = payload["data"]["program"]["id"]
        assert get_program(handler_b, program_id)[0] == 403
        assert patch_program(handler_student, program_id, {"title": "No access"})[0] == 403
        assert program_classes(handler_a, program_id, {"classIds": [class_b["id"]]})[0] == 403
        assert program_classes(handler_a, program_id, {"classIds": [class_a["id"]]})[0] == 200
        assert program_status(handler_a, program_id, {"status": "published"})[0] == 200

        status, payload = post_material(handler_a, program_id, {"title": "Draft guide", "description": "Hidden first", "resourceType": "teacher-note"})
        material_id = payload["data"]["material"]["id"]
        assert status == 201
        status, payload = post_activity(handler_a, program_id, {"title": "Draft walk", "description": "Hidden first", "activityType": "outdoor"})
        activity_id = payload["data"]["activity"]["id"]
        assert status == 201

        status, payload = get_my_program(handler_student, program_id)
        assert status == 200
        assert len(payload["data"]["program"]["materials"]) == 1
        assert len(payload["data"]["program"]["activities"]) == 1

        assert material_status(handler_b, material_id, {"status": "published"})[0] == 403
        assert activity_status(handler_b, activity_id, {"status": "published"})[0] == 403
        assert material_status(handler_a, material_id, {"status": "published"})[0] == 200
        assert activity_status(handler_a, activity_id, {"status": "published"})[0] == 200
        status, payload = get_my_program(handler_student, program_id)
        assert len(payload["data"]["program"]["materials"]) == 1
        assert len(payload["data"]["program"]["activities"]) == 1

        other_program = post_program(handler_b, {"title": "Other Program"})[1]["data"]["program"]
        assert program_classes(handler_b, other_program["id"], {"classIds": [class_b["id"]]})[0] == 200
        assert program_status(handler_b, other_program["id"], {"status": "published"})[0] == 200
        assert get_my_program(handler_student, other_program["id"])[0] == 403

        assert handle_remove_student(handler_b, class_a["id"], student["id"])[0] == 403
        assert handle_remove_student(handler_a, class_a["id"], student["id"])[0] == 200
        print("teacher learning management tests passed")
    finally:
        for filename in FILES:
            target = DATA_DIR / filename
            backup = backup_dir / filename
            if filename in existed:
                shutil.copy2(backup, target)
            elif target.exists():
                target.unlink()
        shutil.rmtree(backup_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
