from __future__ import annotations

import base64
import binascii
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AVATARS_DIR = ROOT / "data" / "avatars"
MAX_AVATAR_BYTES = 512 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _paths_for_user(user_id: str) -> list[Path]:
    return list(AVATARS_DIR.glob(f"{user_id}.*"))


def delete_avatar(user_id: str) -> None:
    for path in _paths_for_user(user_id):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def save_avatar_from_base64(user_id: str, image_b64: str, content_type: str) -> tuple[str | None, str | None]:
    ct = str(content_type or "").strip().lower()
    ext = ALLOWED_CONTENT_TYPES.get(ct)
    if not ext:
        return None, "Unsupported image type. Use JPEG, PNG, or WebP."

    try:
        raw = base64.b64decode(str(image_b64 or "").strip(), validate=True)
    except (binascii.Error, ValueError):
        return None, "Invalid image data."

    if len(raw) > MAX_AVATAR_BYTES:
        return None, f"Image too large (max {MAX_AVATAR_BYTES // 1024} KB)."

    if ct == "image/jpeg" and raw[:3] != b"\xff\xd8\xff":
        return None, "File is not a valid JPEG."
    if ct == "image/png" and raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None, "File is not a valid PNG."
    if ct == "image/webp" and raw[:4] != b"RIFF":
        return None, "File is not a valid WebP."

    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    delete_avatar(user_id)
    filename = f"{user_id}{ext}"
    path = AVATARS_DIR / filename
    path.write_bytes(raw)
    return filename, None


def get_avatar_file(user_id: str) -> tuple[Path | None, str | None]:
    matches = _paths_for_user(user_id)
    if not matches:
        return None, None
    path = matches[0]
    ct = next((k for k, v in ALLOWED_CONTENT_TYPES.items() if v == path.suffix.lower()), "image/jpeg")
    return path, ct
