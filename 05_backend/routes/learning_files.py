from api.errors import error_body
from auth.middleware import require_auth
from models.activity_attachment_storage import read
from models.learning_activity_repository import find_by_id, list_for_program
from models.program_repository import find_by_id
from services.learning_access_service import AccessError, require_student_activity, require_teacher_activity


def activity_file(handler, file_id):
    actor, err = require_auth(handler)
    if err: return 401, None, None, None, err
    activity = None
    from models.json_store import read_rows
    for candidate in read_rows("learning_activities.json"):
        if any(item.get("id") == file_id for item in candidate.get("attachments") or []): activity = candidate; break
    material = None
    if not activity:
        material = next((row for row in read_rows("materials.json") if any(item.get("id") == file_id for item in row.get("attachments") or [])), None)
    if not activity and not material: return 404, None, None, None, error_body("NOT_FOUND", "File not found.")
    try:
        if actor["role"] == "STUDENT":
            if activity: require_student_activity(actor["id"], activity["id"])
            else:
                from services.learning_access_service import require_student_program
                require_student_program(actor["id"], material["programId"])
                if material.get("status") != "published": raise AccessError("FORBIDDEN")
        elif actor["role"] == "TEACHER":
            if activity: require_teacher_activity(actor["id"], activity["id"])
            else:
                from services.ownership_service import owned_program
                owned_program(actor["id"], material["programId"])
        else: raise AccessError("FORBIDDEN")
    except ValueError as exc: return 403, None, None, None, error_body("FORBIDDEN", "File access denied.")
    data, content_type, name = read(file_id)
    if not data: return 404, None, None, None, error_body("NOT_FOUND", "File not found.")
    return 200, data, content_type, name, None
