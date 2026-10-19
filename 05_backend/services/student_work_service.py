from __future__ import annotations

from urllib.parse import urlparse

from models.learning_activity_repository import find_by_id as find_activity, list_for_program
from models.material_repository import find_by_id as find_material, list_for_program as list_materials
from models.program_repository import find_by_id as find_program
from models.user_repository import find_by_id as find_user
from models.work_repository import create_row, delete_row, find_row, list_rows, update_row
from services.learning_access_service import (
    AccessError, require_student_activity, require_student_program,
    require_teacher_activity, require_teacher_student,
    require_teacher_submission_relationship,
)

SUBMISSIONS = "submissions.json"
FEEDBACK = "feedback.json"
CONVERSATIONS = "conversations.json"
MESSAGES = "messages.json"
PORTFOLIO = "portfolio_items.json"
LIBRARY = "library_items.json"


def _text(value, limit: int, required=False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError("REQUIRED")
    if len(text) > limit:
        raise ValueError("TOO_LONG")
    return text


def safe_url(value) -> str | None:
    url = _text(value, 2000)
    if not url:
        return None
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else None


def student_materials(student_id: str, program_id: str) -> list[dict]:
    require_student_program(student_id, program_id)
    return [_material_projection(row) for row in list_materials(program_id) if row.get("status") == "published"]


def student_material(student_id: str, material_id: str) -> dict:
    row = find_material(material_id)
    if not row or row.get("status") != "published":
        raise AccessError("NOT_FOUND")
    require_student_program(student_id, row["programId"])
    return _material_projection(row)


def _material_projection(row: dict) -> dict:
    return {**row, "resourceRef": safe_url(row.get("resourceRef"))}


def submission_for(student_id: str, activity_id: str) -> dict | None:
    return next((row for row in list_rows(SUBMISSIONS) if row.get("studentId") == student_id and row.get("activityId") == activity_id), None)


def student_activities(student_id: str) -> list[dict]:
    from services.program_service import student_programs
    submissions = {(row["activityId"], row["studentId"]): row for row in list_rows(SUBMISSIONS)}
    result = []
    for program in student_programs(student_id):
        for activity in list_for_program(program["id"]):
            if activity.get("status") not in {"published", "closed"}:
                continue
            submission = submissions.get((activity["id"], student_id))
            result.append({**activity, "programTitle": program["title"], "submissionStatus": (submission or {}).get("status", "not_submitted"), "submissionId": (submission or {}).get("id")})
    return sorted(result, key=lambda row: row.get("dueDate") or "9999")


def student_activity(student_id: str, activity_id: str) -> dict:
    row = require_student_activity(student_id, activity_id)
    program = find_program(row["programId"])
    submission = submission_for(student_id, activity_id)
    return {**row, "programTitle": (program or {}).get("title"), "submissionStatus": (submission or {}).get("status", "not_submitted"), "submission": submission}


def save_submission(student_id: str, activity_id: str, body: dict) -> dict:
    activity = require_student_activity(student_id, activity_id)
    existing = submission_for(student_id, activity_id)
    if activity.get("status") == "closed" and not (existing and existing.get("status") in {"draft", "returned"}):
        raise ValueError("ACTIVITY_CLOSED")
    content = _text(body.get("content"), 10000)
    notes = _text(body.get("notes"), 2000)
    action = str(body.get("action") or "submit")
    if action not in {"save", "submit"}:
        raise ValueError("INVALID_ACTION")
    attachments = body.get("attachments") or []
    if not isinstance(attachments, list) or len(attachments) > 5:
        raise ValueError("INVALID_ATTACHMENTS")
    clean_attachments = [{key: item.get(key) for key in ("id", "name", "contentType", "size", "url") if item.get(key) is not None} for item in attachments if isinstance(item, dict)]
    if not content and not clean_attachments:
        raise ValueError("EMPTY_SUBMISSION")
    if existing and existing.get("status") in {"submitted", "reviewed"}:
        raise ValueError("SUBMISSION_LOCKED")
    content_types = [str(item.get("contentType") or "") for item in clean_attachments]
    submission_type = "mixed" if len({"video" if value.startswith("video/") else "photo" if value.startswith("image/") else "file" for value in content_types}) > 1 else ("video" if any(value.startswith("video/") for value in content_types) else "photo" if any(value.startswith("image/") for value in content_types) else "file")
    values = {"content": content, "notes": notes, "submissionType": submission_type, "attachments": clean_attachments, "status": "draft" if action == "save" else "submitted"}
    from models.json_store import now_iso
    values["submittedAt"] = now_iso() if action == "submit" else existing.get("submittedAt") if existing else None
    if existing:
        return update_row(SUBMISSIONS, existing["id"], values, set(values)) or existing
    return create_row(SUBMISSIONS, "sub", {"activityId": activity_id, "studentId": student_id, **values})


def update_my_submission(student_id: str, submission_id: str, body: dict) -> dict:
    row = find_row(SUBMISSIONS, submission_id)
    if not row:
        raise AccessError("NOT_FOUND")
    if row.get("studentId") != student_id:
        raise AccessError("FORBIDDEN")
    return save_submission(student_id, row["activityId"], body)


def teacher_submissions(teacher_id: str, activity_id: str, status=None) -> list[dict]:
    activity = require_teacher_activity(teacher_id, activity_id)
    allowed_students = set()
    from models.program_class_repository import class_ids_for_program
    from models.enrollment_repository import list_student_ids_for_class
    for class_id in class_ids_for_program(activity["programId"]):
        from models.class_repository import find_by_id as find_class
        class_row = find_class(class_id)
        if class_row and class_row.get("teacherId") == teacher_id:
            allowed_students.update(list_student_ids_for_class(class_id))
    users = {student_id: find_user(student_id) for student_id in allowed_students}
    rows = [row for row in list_rows(SUBMISSIONS) if row.get("activityId") == activity_id and row.get("studentId") in allowed_students and row.get("status") in {"submitted", "reviewed", "returned"}]
    if status in {"submitted", "reviewed"}:
        rows = [row for row in rows if row.get("status") == status]
    return [{**row, "student": {"id": row["studentId"], "name": (users.get(row["studentId"]) or {}).get("name", "Student")}} for row in rows]


def teacher_submission(teacher_id: str, submission_id: str) -> dict:
    row = find_row(SUBMISSIONS, submission_id)
    if not row:
        raise AccessError("NOT_FOUND")
    if row.get("status") == "draft":
        raise AccessError("NOT_FOUND")
    activity = require_teacher_submission_relationship(teacher_id, row)
    student = find_user(row["studentId"]) or {}
    return {**row, "activity": activity, "student": {"id": row["studentId"], "name": student.get("name", "Student")}, "feedback": feedback_for_submission(row["id"])}


def return_submission(teacher_id: str, submission_id: str, body: dict) -> dict:
    row = find_row(SUBMISSIONS, submission_id)
    if not row:
        raise AccessError("NOT_FOUND")
    require_teacher_submission_relationship(teacher_id, row)
    if row.get("status") not in {"submitted", "reviewed"}:
        raise ValueError("INVALID_STATUS")
    returned = update_row(SUBMISSIONS, submission_id, {"status": "returned", "returnNote": _text(body.get("note"), 1000)}, {"status", "returnNote"}) or row
    from services.notification_service import notify
    notify(row["studentId"], "submission", "Submission returned", body.get("note") or "Your teacher returned this work for changes.", submission_id)
    return returned


def feedback_for_submission(submission_id: str) -> list[dict]:
    return sorted([row for row in list_rows(FEEDBACK) if row.get("submissionId") == submission_id], key=lambda row: row.get("createdAt", ""))


def add_feedback(actor: dict, submission_id: str, body: dict) -> dict:
    submission = find_row(SUBMISSIONS, submission_id)
    if not submission:
        raise AccessError("NOT_FOUND")
    parent_id = body.get("parentFeedbackId") or None
    if actor["role"] == "TEACHER":
        require_teacher_submission_relationship(actor["id"], submission)
        if submission.get("status") not in {"submitted", "reviewed"}:
            raise ValueError("INVALID_STATUS")
        author_role = "TEACHER"
        teacher_id = actor["id"]
    else:
        if submission.get("studentId") != actor["id"]:
            raise AccessError("FORBIDDEN")
        parent = find_row(FEEDBACK, parent_id) if parent_id else None
        if not parent or parent.get("submissionId") != submission_id or parent.get("authorRole") != "TEACHER":
            raise ValueError("REPLY_REQUIRED")
        author_role = "STUDENT"
        teacher_id = None
    row = create_row(FEEDBACK, "fb", {"submissionId": submission_id, "teacherId": teacher_id, "studentId": submission["studentId"], "authorId": actor["id"], "authorRole": author_role, "parentFeedbackId": parent_id, "content": _text(body.get("content"), 3000, True)})
    if author_role == "TEACHER":
        update_row(SUBMISSIONS, submission_id, {"status": "reviewed"}, {"status"})
    return row


def edit_feedback(teacher_id: str, feedback_id: str, body: dict) -> dict:
    row = find_row(FEEDBACK, feedback_id)
    if not row:
        raise AccessError("NOT_FOUND")
    if row.get("teacherId") != teacher_id:
        raise AccessError("FORBIDDEN")
    return update_row(FEEDBACK, feedback_id, {"content": _text(body.get("content"), 3000, True)}, {"content"}) or row


def my_feedback(student_id: str, submission_id: str) -> list[dict]:
    submission = find_row(SUBMISSIONS, submission_id)
    if not submission or submission.get("studentId") != student_id:
        raise AccessError("FORBIDDEN")
    return feedback_for_submission(submission_id)


def get_or_create_conversation(actor: dict, other_id: str) -> dict:
    other = find_user(other_id)
    if not other or actor["role"] == other.get("role"):
        raise AccessError("FORBIDDEN")
    teacher_id = actor["id"] if actor["role"] == "TEACHER" else other_id
    student_id = actor["id"] if actor["role"] == "STUDENT" else other_id
    require_teacher_student(teacher_id, student_id)
    existing = next((row for row in list_rows(CONVERSATIONS) if row.get("teacherId") == teacher_id and row.get("studentId") == student_id), None)
    row = existing or create_row(CONVERSATIONS, "conv", {"teacherId": teacher_id, "studentId": student_id})
    other = find_user(other_id) or {}
    return {**row, "participant": {"id": other_id, "name": other.get("name", "User")}}


def _conversation(actor: dict, conversation_id: str) -> dict:
    row = find_row(CONVERSATIONS, conversation_id)
    if not row or actor["id"] not in {row.get("teacherId"), row.get("studentId")}:
        raise AccessError("FORBIDDEN")
    require_teacher_student(row["teacherId"], row["studentId"])
    return row


def conversations(actor: dict) -> list[dict]:
    if actor["role"] == "STUDENT":
        from models.class_repository import find_by_id as find_class
        from models.enrollment_repository import list_for_student
        for enrollment in list_for_student(actor["id"]):
            class_row = find_class(enrollment["classId"])
            if class_row and class_row.get("teacherId"):
                get_or_create_conversation(actor, class_row["teacherId"])
    key = "teacherId" if actor["role"] == "TEACHER" else "studentId"
    result = []
    messages = list_rows(MESSAGES)
    for row in list_rows(CONVERSATIONS):
        if row.get(key) != actor["id"]:
            continue
        other_id = row["studentId"] if actor["role"] == "TEACHER" else row["teacherId"]
        other = find_user(other_id) or {}
        latest = next(iter(sorted([m for m in messages if m.get("conversationId") == row["id"]], key=lambda m: m.get("createdAt", ""), reverse=True)), None)
        unread_count = len([
            message for message in messages
            if message.get("conversationId") == row["id"]
            and message.get("senderId") != actor["id"]
            and not message.get("readAt")
        ])
        result.append({**row, "participant": {"id": other_id, "name": other.get("name", "User")}, "latestMessage": latest, "unreadCount": unread_count})
    return sorted(result, key=lambda row: (row.get("latestMessage") or {}).get("createdAt") or row.get("createdAt", ""), reverse=True)


def conversation_messages(actor: dict, conversation_id: str) -> list[dict]:
    _conversation(actor, conversation_id)
    return sorted([row for row in list_rows(MESSAGES) if row.get("conversationId") == conversation_id], key=lambda row: row.get("createdAt", ""))


def send_message(actor: dict, conversation_id: str, body: dict) -> dict:
    conversation = _conversation(actor, conversation_id)
    row = create_row(MESSAGES, "msg", {"conversationId": conversation_id, "senderId": actor["id"], "content": _text(body.get("content"), 2000, True), "readAt": None})
    from services.notification_service import notify
    recipient_id = conversation["studentId"] if actor["id"] == conversation["teacherId"] else conversation["teacherId"]
    sender = find_user(actor["id"]) or {}
    notify(recipient_id, "message", f"Message from {sender.get('name', 'a class member')}", row["content"][:120], conversation_id)
    return row


def mark_read(actor: dict, conversation_id: str) -> int:
    _conversation(actor, conversation_id)
    count = 0
    for row in list_rows(MESSAGES):
        if row.get("conversationId") == conversation_id and row.get("senderId") != actor["id"] and not row.get("readAt"):
            from models.json_store import now_iso
            update_row(MESSAGES, row["id"], {"readAt": now_iso()}, {"readAt"}); count += 1
    from services.notification_service import mark_read as mark_notifications_read
    for notice in list_rows("notifications.json"):
        if notice.get("userId") == actor["id"] and notice.get("kind") == "message" and notice.get("resourceId") == conversation_id and not notice.get("readAt"):
            mark_notifications_read(actor["id"], notification_id=notice["id"])
    return count


def my_portfolio(student_id: str) -> list[dict]:
    submissions = {row["id"]: row for row in list_rows(SUBMISSIONS) if row.get("studentId") == student_id}
    return [{**row, "submission": submissions.get(row["submissionId"])} for row in sorted(list_rows(PORTFOLIO), key=lambda x: x.get("displayOrder", 0)) if row.get("studentId") == student_id and row.get("submissionId") in submissions]


def add_portfolio_item(student_id: str, body: dict) -> dict:
    submission = find_row(SUBMISSIONS, str(body.get("submissionId") or ""))
    if not submission or submission.get("studentId") != student_id:
        raise AccessError("FORBIDDEN")
    if submission.get("status") not in {"submitted", "reviewed"}:
        raise ValueError("SUBMISSION_NOT_FINAL")
    existing = next((row for row in list_rows(PORTFOLIO) if row.get("studentId") == student_id and row.get("submissionId") == submission["id"]), None)
    if existing:
        return existing
    return create_row(PORTFOLIO, "port", {"studentId": student_id, "submissionId": submission["id"], "caption": _text(body.get("caption"), 500), "displayOrder": len(my_portfolio(student_id))})


def update_portfolio_item(student_id: str, item_id: str, body: dict) -> dict:
    row = find_row(PORTFOLIO, item_id)
    if not row or row.get("studentId") != student_id:
        raise AccessError("FORBIDDEN")
    patch = {}
    if "caption" in body: patch["caption"] = _text(body.get("caption"), 500)
    if "displayOrder" in body: patch["displayOrder"] = max(0, int(body["displayOrder"]))
    return update_row(PORTFOLIO, item_id, patch, {"caption", "displayOrder"}) or row


def remove_portfolio_item(student_id: str, item_id: str) -> bool:
    row = find_row(PORTFOLIO, item_id)
    if not row or row.get("studentId") != student_id:
        raise AccessError("FORBIDDEN")
    return delete_row(PORTFOLIO, item_id)


def upsert_library_item(teacher_id: str, submission_id: str, body: dict) -> dict:
    submission = find_row(SUBMISSIONS, submission_id)
    if not submission:
        raise AccessError("NOT_FOUND")
    activity = require_teacher_submission_relationship(teacher_id, submission)
    from models.program_class_repository import class_ids_for_program
    class_ids = sorted(set(class_ids_for_program(activity["programId"])).intersection(require_teacher_student(teacher_id, submission["studentId"])))
    status = str(body.get("status") or "published")
    if status not in {"draft", "published", "withdrawn"}: raise ValueError("INVALID_STATUS")
    values = {"publicTitle": _text(body.get("publicTitle"), 200, True), "publicDescription": _text(body.get("publicDescription"), 1000), "status": status, "publishedAt": None, "classId": class_ids[0] if class_ids else None}
    if status == "published":
        from models.json_store import now_iso
        values["publishedAt"] = now_iso()
    existing = next((row for row in list_rows(LIBRARY) if row.get("submissionId") == submission_id), None)
    if existing:
        return update_row(LIBRARY, existing["id"], values, set(values)) or existing
    return create_row(LIBRARY, "lib", {"submissionId": submission_id, "publishedBy": teacher_id, **values})


def student_library_status(student_id: str, submission_id: str) -> dict | None:
    submission = find_row(SUBMISSIONS, submission_id)
    if not submission or submission.get("studentId") != student_id: raise AccessError("FORBIDDEN")
    row = next((item for item in list_rows(LIBRARY) if item.get("submissionId") == submission_id), None)
    return {key: row.get(key) for key in ("id", "publicTitle", "publicDescription", "status", "publishedAt")} if row else None


def public_library_projection(row: dict) -> dict:
    return {key: row.get(key) for key in ("id", "publicTitle", "publicDescription", "status", "publishedAt", "classId")}
