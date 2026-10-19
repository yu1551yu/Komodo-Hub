from api.errors import error_body, success_body
from auth.middleware import get_current_user, require_auth, require_role
from services.community_service import add_comment, create_student_post, image_bytes, list_posts, pending_for_teacher, review_post, student_posts, upload_student_image


def _error(exc):
    code = str(exc); return (404 if code == "NOT_FOUND" else 403 if code == "FORBIDDEN" else 400), error_body(code if code in {"NOT_FOUND", "FORBIDDEN"} else "VALIDATION_ERROR", "The community request is not allowed." if code == "FORBIDDEN" else "Invalid community content.")


def posts(handler): return 200, success_body({"posts": list_posts()})
def comment(handler, post_id, body):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 201, success_body({"comment": add_comment(actor, post_id, body)})
    except ValueError as exc: return _error(exc)
def student_post(handler, body):
    actor, err = require_role(handler, "STUDENT")
    if err: return (401 if err["error"]["code"] == "UNAUTHORIZED" else 403), err
    try: return 201, success_body({"post": create_student_post(actor["id"], body)})
    except ValueError as exc: return _error(exc)
def my_posts(handler):
    actor, err = require_role(handler, "STUDENT")
    if err: return (401 if err["error"]["code"] == "UNAUTHORIZED" else 403), err
    return 200, success_body({"posts": student_posts(actor["id"])})
def student_image(handler, body):
    actor, err = require_role(handler, "STUDENT")
    if err: return (401 if err["error"]["code"] == "UNAUTHORIZED" else 403), err
    try: return 201, success_body({"attachment": upload_student_image(actor["id"], body)})
    except ValueError as exc: return _error(exc)
def teacher_pending(handler):
    actor, err = require_role(handler, "TEACHER")
    if err: return (401 if err["error"]["code"] == "UNAUTHORIZED" else 403), err
    return 200, success_body({"posts": pending_for_teacher(actor["id"])})
def teacher_review(handler, post_id, body):
    actor, err = require_role(handler, "TEACHER")
    if err: return (401 if err["error"]["code"] == "UNAUTHORIZED" else 403), err
    try: return 200, success_body({"post": review_post(actor["id"], post_id, body)})
    except ValueError as exc: return _error(exc)
def image(handler, file_id):
    data, content_type = image_bytes(file_id, get_current_user(handler))
    if not data: return 404, None, None, error_body("NOT_FOUND", "Image not found.")
    return 200, data, content_type, None
