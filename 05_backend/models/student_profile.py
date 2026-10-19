from __future__ import annotations

import re
from typing import Any

AVATAR_PRESETS: dict[str, str] = {
    "avatar-komodo": "Komodo dragon",
    "avatar-owl": "Owl",
    "avatar-turtle": "Sea turtle",
    "avatar-leaf": "Leaf",
    "avatar-backpack": "Backpack",
}

PROFILE_BACKGROUNDS = frozenset({"forest", "ocean", "sunrise", "dusk"})

BACKGROUND_THEMES: dict[str, dict[str, str]] = {
    "forest": {"label": "Forest", "accent": "#3D5A80", "paper": "#F6FAF7", "sidebar": "#1A2A3D"},
    "ocean": {"label": "Ocean", "accent": "#2563EB", "paper": "#F0F6FB", "sidebar": "#0F2744"},
    "sunrise": {"label": "Sunrise", "accent": "#C2410C", "paper": "#FDF8F3", "sidebar": "#3D2817"},
    "dusk": {"label": "Dusk", "accent": "#5B4B8A", "paper": "#F5F3F8", "sidebar": "#2A2438"},
}

DEFAULT_AVATAR_ID = "avatar-komodo"
DEFAULT_THEME_COLOR = "#3d5a80"
DEFAULT_PROFILE_BG = "forest"
MAX_SIGNATURE_LEN = 160
MAX_NICKNAME_LEN = 40

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
ALLOWED_GENDERS = frozenset({"M", "F", "", "prefer-not-to-say"})

PATCHABLE_ROOT_KEYS = frozenset(
    {"nickname", "signature", "gender", "avatarId", "profileBg"}
)


def default_student_profile() -> dict[str, str]:
    return {
        "avatarType": "preset",
        "avatarId": DEFAULT_AVATAR_ID,
        "avatarFile": "",
        "themeColor": DEFAULT_THEME_COLOR,
        "profileBg": DEFAULT_PROFILE_BG,
        "signature": "",
        "gender": "",
        "nickname": "",
    }


def _normalize_gender(value: str | None) -> str:
    g = str(value or "").strip()
    if g in ("prefer-not-to-say", "P"):
        return ""
    return g if g in ("M", "F", "") else ""


def ensure_student_profile(user: dict[str, Any]) -> dict[str, str]:
    profile = user.get("studentProfile")
    if not isinstance(profile, dict):
        profile = default_student_profile()
    else:
        profile = {
            "avatarType": profile.get("avatarType") or "preset",
            "avatarId": profile.get("avatarId") or DEFAULT_AVATAR_ID,
            "avatarFile": str(profile.get("avatarFile") or ""),
            "themeColor": profile.get("themeColor") or DEFAULT_THEME_COLOR,
            "profileBg": profile.get("profileBg") or DEFAULT_PROFILE_BG,
            "signature": str(profile.get("signature") or "")[:MAX_SIGNATURE_LEN],
            "gender": _normalize_gender(profile.get("gender")),
            "nickname": str(profile.get("nickname") or "").strip()[:MAX_NICKNAME_LEN],
        }
    if profile["avatarType"] not in ("preset", "upload"):
        profile["avatarType"] = "preset"
    if profile["avatarId"] not in AVATAR_PRESETS:
        profile["avatarId"] = DEFAULT_AVATAR_ID
    if profile["profileBg"] not in PROFILE_BACKGROUNDS:
        profile["profileBg"] = DEFAULT_PROFILE_BG
    theme = BACKGROUND_THEMES.get(profile["profileBg"], BACKGROUND_THEMES[DEFAULT_PROFILE_BG])
    profile["themeColor"] = theme["accent"]
    return profile


def _public_display_name(user: dict[str, Any], profile: dict[str, str]) -> str:
    nick = str(profile.get("nickname") or "").strip()
    real = str(user.get("name") or "").strip()
    return nick or real


def student_profile_response(user: dict[str, Any]) -> dict[str, Any]:
    profile = ensure_student_profile(user)
    avatar_url = None
    if profile["avatarType"] == "upload" and profile.get("avatarFile"):
        avatar_url = "/api/students/me/avatar"
    return {
        "userId": user["id"],
        "email": user["email"],
        "role": user["role"],
        "realName": user.get("name", ""),
        "nickname": profile.get("nickname", ""),
        "displayName": _public_display_name(user, profile),
        "signature": profile["signature"],
        "gender": profile["gender"],
        "avatarType": profile["avatarType"],
        "avatarId": profile["avatarId"],
        "avatarUrl": avatar_url,
        "avatarLabel": AVATAR_PRESETS.get(profile["avatarId"], "Avatar"),
        "themeColor": profile["themeColor"],
        "profileBg": profile["profileBg"],
        "backgroundOptions": [
            {"id": k, **v} for k, v in BACKGROUND_THEMES.items()
        ],
        "updatedAt": user.get("updatedAt"),
        "createdAt": user.get("createdAt"),
    }
