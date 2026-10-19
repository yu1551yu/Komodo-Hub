from __future__ import annotations

import base64
import binascii
from pathlib import Path
from models.json_store import new_id

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "submission_uploads"
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf", "application/msword": ".doc", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx", "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
MAX_BYTES = 25 * 1024 * 1024


def save_attachment(student_id: str, payload: dict) -> dict:
    content_type = str(payload.get("contentType") or "")
    if content_type not in ALLOWED: raise ValueError("UNSUPPORTED_ATTACHMENT")
    try: data = base64.b64decode(str(payload.get("fileBase64") or payload.get("imageBase64") or ""), validate=True)
    except (binascii.Error, ValueError): raise ValueError("INVALID_ATTACHMENT")
    if not data or len(data) > MAX_BYTES: raise ValueError("ATTACHMENT_SIZE")
    attachment_id = new_id("att"); folder = UPLOAD_DIR / student_id; folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{attachment_id}{ALLOWED[content_type]}"; path.write_bytes(data)
    return {"id": attachment_id, "name": str(payload.get("name") or path.name)[:200], "contentType": content_type, "size": len(data), "url": f"/api/submission-files/{attachment_id}"}


def read_attachment(student_id: str, attachment_id: str):
    folder = UPLOAD_DIR / student_id
    for content_type, suffix in ALLOWED.items():
        path = folder / f"{attachment_id}{suffix}"
        if path.is_file(): return path.read_bytes(), content_type
    return None, None
