from __future__ import annotations

import base64
import binascii
from pathlib import Path
from models.json_store import new_id

DIR = Path(__file__).resolve().parent.parent / "data" / "activity_attachments"
TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}
EXTENSION_TYPES = {suffix: content_type for content_type, suffix in TYPES.items()}


def save(payload: dict) -> dict:
    content_type = str(payload.get("contentType") or "")
    name = str(payload.get("name") or "resource")[:200]
    name_suffix = Path(name).suffix.lower()
    suffix = TYPES.get(content_type) or (name_suffix if name_suffix in EXTENSION_TYPES else None)
    if not suffix: raise ValueError("UNSUPPORTED_ATTACHMENT")
    content_type = content_type if content_type in TYPES else EXTENSION_TYPES[suffix]
    try: data = base64.b64decode(str(payload.get("fileBase64") or ""), validate=True)
    except (binascii.Error, ValueError): raise ValueError("INVALID_ATTACHMENT")
    if not data or len(data) > 20 * 1024 * 1024: raise ValueError("ATTACHMENT_SIZE")
    file_id = new_id("activity_file"); DIR.mkdir(parents=True, exist_ok=True); (DIR / f"{file_id}{suffix}").write_bytes(data)
    return {"id": file_id, "name": name, "contentType": content_type, "size": len(data), "url": f"/api/learning-files/{file_id}"}


def read(file_id: str):
    for content_type, suffix in TYPES.items():
        path = DIR / f"{file_id}{suffix}"
        if path.is_file(): return path.read_bytes(), content_type, path.name
    return None, None, None
