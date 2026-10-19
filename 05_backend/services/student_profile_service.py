from __future__ import annotations

from api.errors import error_body, success_body
from models.avatar_storage import delete_avatar, get_avatar_file, save_avatar_from_base64
from models.student_profile import (
    AVATAR_PRESETS,
    MAX_NICKNAME_LEN,
    MAX_SIGNATURE_LEN,
    PATCHABLE_ROOT_KEYS,
    PROFILE_BACKGROUNDS,
    _normalize_gender,
    ensure_student_profile,
    student_profile_response,
)
from models.user_repository import find_by_id, update_user


def get_student_profile(student_id: str) -> tuple[int, dict]:
    user = find_by_id(student_id)
    if not user or user.get("role") != "STUDENT":
        return 403, error_body("FORBIDDEN", "Student profile is only available to student accounts.")
    normalized = ensure_student_profile(user)
    if user.get("studentProfile") != normalized:
        update_user(student_id, {"studentProfile": normalized})
        user = find_by_id(student_id) or user
    return 200, success_body({"profile": student_profile_response(user)})


def patch_student_profile(student_id: str, body: dict | None) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, error_body("INVALID_BODY", "Request body must be JSON.")

    unknown = set(body.keys()) - PATCHABLE_ROOT_KEYS
    if unknown:
        return 400, error_body(
            "VALIDATION_ERROR",
            "Only nickname, signature, gender, avatarId, and profileBg may be updated.",
            {"fields": sorted(unknown)},
        )
    if not body:
        return 400, error_body("VALIDATION_ERROR", "No profile fields to update.")

    user = find_by_id(student_id)
    if not user or user.get("role") != "STUDENT":
        return 403, error_body("FORBIDDEN", "Student profile is only available to student accounts.")

    patch_user: dict = {}
    profile = ensure_student_profile(user)

    if "nickname" in body:
        nick = str(body["nickname"] or "").strip()
        if nick and len(nick) < 2:
            return 400, error_body(
                "VALIDATION_ERROR",
                "Nickname must be at least 2 characters (or leave empty).",
                {"field": "nickname"},
            )
        if len(nick) > MAX_NICKNAME_LEN:
            return 400, error_body(
                "VALIDATION_ERROR",
                f"Nickname must be at most {MAX_NICKNAME_LEN} characters.",
                {"field": "nickname"},
            )
        profile["nickname"] = nick

    if "signature" in body:
        sig = str(body["signature"] or "").strip()
        if len(sig) > MAX_SIGNATURE_LEN:
            return 400, error_body(
                "VALIDATION_ERROR",
                f"Signature must be at most {MAX_SIGNATURE_LEN} characters.",
                {"field": "signature"},
            )
        profile["signature"] = sig

    if "gender" in body:
        profile["gender"] = _normalize_gender(body.get("gender"))

    if "avatarId" in body:
        aid = str(body["avatarId"] or "").strip()
        if aid not in AVATAR_PRESETS:
            return 400, error_body(
                "VALIDATION_ERROR",
                "Invalid avatar selection.",
                {"field": "avatarId"},
            )
        profile["avatarId"] = aid
        profile["avatarType"] = "preset"
        profile["avatarFile"] = ""
        delete_avatar(student_id)

    if "profileBg" in body:
        bg = str(body["profileBg"] or "").strip()
        if bg not in PROFILE_BACKGROUNDS:
            return 400, error_body(
                "VALIDATION_ERROR",
                "Invalid background theme.",
                {"field": "profileBg"},
            )
        profile["profileBg"] = bg

    profile = ensure_student_profile({**user, "studentProfile": profile})
    patch_user["studentProfile"] = profile
    updated = update_user(student_id, patch_user)
    if not updated:
        return 404, error_body("NOT_FOUND", "User not found.")
    return 200, success_body({"profile": student_profile_response(updated)})


def upload_student_avatar(student_id: str, body: dict | None) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, error_body("INVALID_BODY", "Request body must be JSON.")
    user = find_by_id(student_id)
    if not user or user.get("role") != "STUDENT":
        return 403, error_body("FORBIDDEN", "Student profile is only available to student accounts.")

    filename, err = save_avatar_from_base64(
        student_id,
        str(body.get("imageBase64") or ""),
        str(body.get("contentType") or ""),
    )
    if err:
        return 400, error_body("VALIDATION_ERROR", err, {"field": "imageBase64"})

    profile = ensure_student_profile(user)
    profile["avatarType"] = "upload"
    profile["avatarFile"] = filename or ""
    updated = update_user(student_id, {"studentProfile": profile})
    if not updated:
        return 404, error_body("NOT_FOUND", "User not found.")
    return 200, success_body({"profile": student_profile_response(updated)})


def get_student_avatar_bytes(student_id: str) -> tuple[int, bytes | None, str | None, dict | None]:
    user = find_by_id(student_id)
    if not user or user.get("role") != "STUDENT":
        return 403, None, None, error_body("FORBIDDEN", "Not allowed.")
    profile = ensure_student_profile(user)
    if profile["avatarType"] != "upload":
        return 404, None, None, error_body("NOT_FOUND", "No uploaded avatar.")
    path, content_type = get_avatar_file(student_id)
    if not path or not path.is_file():
        return 404, None, None, error_body("NOT_FOUND", "Avatar file missing.")
    return 200, path.read_bytes(), content_type, None
