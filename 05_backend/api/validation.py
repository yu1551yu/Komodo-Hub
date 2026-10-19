from __future__ import annotations

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_REGISTER_ROLES = frozenset({"STUDENT", "TEACHER", "PUBLIC"})


def validate_register(payload: dict) -> tuple[str | None, dict | None]:
    if not isinstance(payload, dict):
        return "INVALID_BODY", None
    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    role = str(payload.get("role") or "").strip().upper()
    if not name or len(name) < 2:
        return "VALIDATION_ERROR", {"field": "name", "message": "Name is required (min 2 characters)."}
    if not EMAIL_RE.match(email):
        return "VALIDATION_ERROR", {"field": "email", "message": "Valid email is required."}
    if len(password) < 6:
        return "VALIDATION_ERROR", {"field": "password", "message": "Password must be at least 6 characters."}
    if role not in ALLOWED_REGISTER_ROLES:
        return "VALIDATION_ERROR", {"field": "role", "message": "Role must be STUDENT, TEACHER or PUBLIC."}
    out = {"name": name, "email": email, "password": password, "role": role}
    if role == "STUDENT":
        access_code = str(payload.get("accessCode") or "").strip()
        if not access_code:
            return "VALIDATION_ERROR", {
                "field": "accessCode",
                "message": "Class access code is required for student registration.",
            }
        out["accessCode"] = access_code
    return None, out


def validate_create_class(payload: dict) -> tuple[str | None, dict | None]:
    if not isinstance(payload, dict):
        return "INVALID_BODY", None
    name = str(payload.get("name") or "").strip()
    if len(name) < 2:
        return "VALIDATION_ERROR", {"field": "name", "message": "Class name is required (min 2 characters)."}
    return None, {"name": name}


def validate_join_class(payload: dict) -> tuple[str | None, dict | None]:
    if not isinstance(payload, dict):
        return "INVALID_BODY", None
    access_code = str(payload.get("accessCode") or "").strip()
    if not access_code:
        return "VALIDATION_ERROR", {"field": "accessCode", "message": "Access code is required."}
    return None, {"accessCode": access_code}


def validate_login(payload: dict) -> tuple[str | None, dict | None]:
    if not isinstance(payload, dict):
        return "INVALID_BODY", None
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not EMAIL_RE.match(email):
        return "VALIDATION_ERROR", {"field": "email", "message": "Valid email is required."}
    if not password:
        return "VALIDATION_ERROR", {"field": "password", "message": "Password is required."}
    return None, {"email": email, "password": password}


def validate_change_password(payload: dict) -> tuple[str | None, dict | None]:
    """Validate a password change without ever echoing password values back."""
    if not isinstance(payload, dict):
        return "INVALID_BODY", None
    current_password = str(payload.get("currentPassword") or "")
    new_password = str(payload.get("newPassword") or "")
    if not current_password:
        return "VALIDATION_ERROR", {
            "field": "currentPassword",
            "message": "Current password is required.",
        }
    # A generous upper bound protects PBKDF2 from unexpectedly large request
    # bodies while still allowing passphrases and password-manager values.
    if len(new_password) < 10 or len(new_password) > 128:
        return "VALIDATION_ERROR", {
            "field": "newPassword",
            "message": "New password must be between 10 and 128 characters.",
        }
    if new_password == current_password:
        return "VALIDATION_ERROR", {
            "field": "newPassword",
            "message": "New password must be different from the current password.",
        }
    return None, {"currentPassword": current_password, "newPassword": new_password}
