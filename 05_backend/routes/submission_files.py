from api.errors import error_body
from auth.middleware import require_auth
from models.submission_storage import read_attachment
from models.work_repository import list_rows
from services.learning_access_service import AccessError, require_teacher_submission_relationship


def submission_file(handler, file_id):
    actor, error = require_auth(handler)
    if error:
        return 401, None, None, error
    submission = next((row for row in list_rows("submissions.json") if any(item.get("id") == file_id for item in row.get("attachments") or [])), None)
    if not submission:
        return 404, None, None, error_body("NOT_FOUND", "File not found.")
    try:
        if actor.get("role") == "STUDENT":
            if submission.get("studentId") != actor["id"]:
                raise AccessError("FORBIDDEN")
        elif actor.get("role") == "TEACHER":
            require_teacher_submission_relationship(actor["id"], submission)
        else:
            raise AccessError("FORBIDDEN")
    except (AccessError, ValueError):
        return 403, None, None, error_body("FORBIDDEN", "File access denied.")
    data, content_type = read_attachment(submission["studentId"], file_id)
    if not data:
        return 404, None, None, error_body("NOT_FOUND", "File not found.")
    return 200, data, content_type, None
