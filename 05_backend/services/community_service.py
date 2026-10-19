from __future__ import annotations

import base64
import binascii
from pathlib import Path

from models.json_store import new_id, now_iso
from models.user_repository import find_by_id
from models.work_repository import create_row, find_row, list_rows, update_row
from services.learning_access_service import require_teacher_student

POSTS = "community_posts.json"
COMMENTS = "community_comments.json"
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "community_uploads"


def _text(value, limit, required=False):
    text = str(value or "").strip()
    if required and len(text) < 2: raise ValueError("REQUIRED")
    if len(text) > limit: raise ValueError("TOO_LONG")
    return text


def _author(user_id: str, role: str) -> dict:
    user = find_by_id(user_id) or {}
    if role == "STUDENT": return {"label": "Student naturalist", "role": role}
    return {"label": user.get("name", "Community member"), "role": role}


def list_posts() -> list[dict]:
    comments = list_rows(COMMENTS)
    rows = []
    for post in list_rows(POSTS):
        if post.get("status") != "approved": continue
        rows.append({**post, "studentId": None, "createdBy": None, "author": _author(post.get("createdBy", ""), post.get("authorRole", "")), "comments": [{**comment, "userId": None} for comment in comments if comment.get("postId") == post["id"]]})
    return sorted(rows, key=lambda row: row.get("createdAt", ""), reverse=True)


def create_student_post(student_id: str, body: dict) -> dict:
    attachment = body.get("attachment") if isinstance(body.get("attachment"), dict) else None
    return create_row(POSTS, "post", {"title": _text(body.get("title"), 160, True), "content": _text(body.get("content"), 5000, True), "species": _text(body.get("species"), 120), "place": _text(body.get("place"), 160), "attachment": attachment, "createdBy": student_id, "authorRole": "STUDENT", "status": "pending_teacher", "reviewedBy": None, "reviewedAt": None})


def student_posts(student_id: str) -> list[dict]:
    return sorted(
        [row for row in list_rows(POSTS) if row.get("createdBy") == student_id],
        key=lambda row: row.get("createdAt", ""),
        reverse=True,
    )


def upload_student_image(student_id: str, body: dict) -> dict:
    content_type = str(body.get("contentType") or "")
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(content_type)
    if not suffix: raise ValueError("UNSUPPORTED_IMAGE")
    try: data = base64.b64decode(str(body.get("imageBase64") or ""), validate=True)
    except (binascii.Error, ValueError): raise ValueError("INVALID_IMAGE")
    if not data or len(data) > 5 * 1024 * 1024: raise ValueError("IMAGE_SIZE")
    file_id = new_id("community"); UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / f"{file_id}{suffix}").write_bytes(data)
    return {"id": file_id, "name": _text(body.get("name"), 200), "contentType": content_type, "size": len(data), "url": f"/api/community/images/{file_id}"}


def image_bytes(file_id: str, actor: dict | None = None):
    post = next((row for row in list_rows(POSTS) if (row.get("attachment") or {}).get("id") == file_id), None)
    if not post: return None, None
    allowed = post.get("status") == "approved" or (actor and actor.get("id") == post.get("createdBy"))
    if actor and actor.get("role") == "TEACHER" and post.get("status") == "pending_teacher":
        try: require_teacher_student(actor["id"], post["createdBy"]); allowed = True
        except ValueError: pass
    if not allowed: return None, None
    for suffix, content_type in ((".jpg", "image/jpeg"), (".png", "image/png"), (".webp", "image/webp")):
        path = UPLOAD_DIR / f"{file_id}{suffix}"
        if path.is_file(): return path.read_bytes(), content_type
    return None, None


def add_comment(actor: dict, post_id: str, body: dict) -> dict:
    post = find_row(POSTS, post_id)
    if not post or post.get("status") != "approved": raise ValueError("NOT_FOUND")
    author = _author(actor["id"], actor["role"])
    return create_row(COMMENTS, "comment", {"postId": post_id, "userId": actor["id"], "authorName": author["label"], "authorRole": actor["role"], "content": _text(body.get("content"), 1000, True)})


def pending_for_teacher(teacher_id: str) -> list[dict]:
    result = []
    for post in list_rows(POSTS):
        if post.get("status") != "pending_teacher": continue
        try: require_teacher_student(teacher_id, post["createdBy"])
        except ValueError: continue
        student = find_by_id(post["createdBy"]) or {}
        result.append({**post, "student": {"id": post["createdBy"], "name": student.get("name", "Student")}})
    return result


def review_post(teacher_id: str, post_id: str, body: dict) -> dict:
    post = find_row(POSTS, post_id)
    if not post: raise ValueError("NOT_FOUND")
    require_teacher_student(teacher_id, post["createdBy"])
    status = str(body.get("status") or "")
    if status not in {"approved", "rejected"}: raise ValueError("INVALID_STATUS")
    updated = update_row(POSTS, post_id, {"status": status, "reviewedBy": teacher_id, "reviewedAt": now_iso(), "reviewNote": _text(body.get("reviewNote"), 1000)}, {"status", "reviewedBy", "reviewedAt", "reviewNote"}) or post
    from services.notification_service import notify
    notify(post["createdBy"], "field_note", "Field note approved" if status == "approved" else "Field note needs changes", post.get("title", "Your field note was reviewed"), post_id)
    return updated
