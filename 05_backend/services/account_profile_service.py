from __future__ import annotations

from api.errors import error_body, success_body
from models.avatar_storage import delete_avatar, get_avatar_file, save_avatar_from_base64
from models.student_profile import AVATAR_PRESETS, BACKGROUND_THEMES, PROFILE_BACKGROUNDS, default_student_profile, ensure_student_profile
from models.user_repository import find_by_id, update_user


def _profile(user: dict) -> dict:
    stored = user.get("accountProfile")
    return ensure_student_profile({**user, "studentProfile": stored if isinstance(stored, dict) else default_student_profile()})


def _response(user: dict) -> dict:
    profile = _profile(user)
    route = {"TEACHER": "teacher", "PUBLIC": "public"}.get(user.get("role"), "students/me")
    return {"userId": user["id"], "email": user.get("email", ""), "role": user["role"], "realName": user.get("name", ""), "nickname": profile["nickname"], "displayName": profile["nickname"] or user.get("name", ""), "signature": profile["signature"], "gender": profile["gender"], "avatarType": profile["avatarType"], "avatarId": profile["avatarId"], "avatarUrl": f"/api/{route}/avatar" if profile["avatarType"] == "upload" else None, "profileBg": profile["profileBg"], "backgroundOptions": [{"id": key, **value} for key, value in BACKGROUND_THEMES.items()], "updatedAt": user.get("updatedAt")}


def get_profile(user_id: str, role: str):
    user = find_by_id(user_id)
    if not user or user.get("role") != role: return 403, error_body("FORBIDDEN", "Profile is not available.")
    return 200, success_body({"profile": _response(user)})


def patch_profile(user_id: str, role: str, body: dict):
    user = find_by_id(user_id)
    if not user or user.get("role") != role: return 403, error_body("FORBIDDEN", "Profile is not available.")
    if not isinstance(body, dict): return 400, error_body("INVALID_BODY", "Request body must be JSON.")
    unknown = set(body) - {"nickname", "signature", "gender", "avatarId", "profileBg"}
    if unknown: return 400, error_body("VALIDATION_ERROR", "Unsupported profile field.", {"fields": sorted(unknown)})
    profile = _profile(user)
    if "nickname" in body:
        value = str(body.get("nickname") or "").strip()
        if value and not 2 <= len(value) <= 40: return 400, error_body("VALIDATION_ERROR", "Nickname must contain 2-40 characters.")
        profile["nickname"] = value
    if "signature" in body:
        value = str(body.get("signature") or "").strip()
        if len(value) > 160: return 400, error_body("VALIDATION_ERROR", "Signature is too long.")
        profile["signature"] = value
    if "gender" in body: profile["gender"] = str(body.get("gender") or "") if str(body.get("gender") or "") in {"", "M", "F"} else ""
    if "profileBg" in body:
        if body["profileBg"] not in PROFILE_BACKGROUNDS: return 400, error_body("VALIDATION_ERROR", "Invalid profile theme.")
        profile["profileBg"] = body["profileBg"]
    if "avatarId" in body:
        if body["avatarId"] not in AVATAR_PRESETS: return 400, error_body("VALIDATION_ERROR", "Invalid avatar.")
        profile.update({"avatarId": body["avatarId"], "avatarType": "preset", "avatarFile": ""}); delete_avatar(user_id)
    updated = update_user(user_id, {"accountProfile": profile})
    return 200, success_body({"profile": _response(updated)})


def upload_avatar(user_id: str, role: str, body: dict):
    user = find_by_id(user_id)
    if not user or user.get("role") != role: return 403, error_body("FORBIDDEN", "Profile is not available.")
    filename, err = save_avatar_from_base64(user_id, str(body.get("imageBase64") or ""), str(body.get("contentType") or ""))
    if err: return 400, error_body("VALIDATION_ERROR", err)
    profile = _profile(user); profile.update({"avatarType": "upload", "avatarFile": filename or ""})
    updated = update_user(user_id, {"accountProfile": profile})
    return 200, success_body({"profile": _response(updated)})


def avatar_bytes(user_id: str, role: str):
    user = find_by_id(user_id)
    if not user or user.get("role") != role: return 403, None, None, error_body("FORBIDDEN", "Not allowed.")
    path, content_type = get_avatar_file(user_id)
    if not path: return 404, None, None, error_body("NOT_FOUND", "Avatar not found.")
    return 200, path.read_bytes(), content_type, None
