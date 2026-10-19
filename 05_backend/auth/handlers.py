from __future__ import annotations

from api.errors import error_body, success_body
from api.validation import validate_change_password, validate_login, validate_register
from auth.middleware import get_current_user, parse_session_token
from auth.passwords import hash_password, verify_password
from auth.sessions import create_session, delete_session
from models.student_profile import default_student_profile
from services import login_rate_limit_service
from models.user_repository import (
    create_user,
    delete_user,
    find_by_email,
    find_by_id,
    public_user,
    seed_users_if_empty,
    update_user,
)
from services.enrollment_service import join_class_by_access_code, resolve_class_by_access_code


def handle_register(body: dict) -> tuple[int, dict]:
    seed_users_if_empty()
    err_code, parsed = validate_register(body)
    if err_code:
        if err_code == "INVALID_BODY":
            return 400, error_body("INVALID_BODY", "Request body must be JSON.")
        return 400, error_body(err_code, parsed["message"], parsed)

    if parsed["role"] == "STUDENT":
        access_code = parsed["accessCode"]
        _, code_err = resolve_class_by_access_code(access_code)
        if code_err:
            return code_err
        try:
            user = create_user(
                parsed["name"],
                parsed["email"],
                parsed["password"],
                parsed["role"],
                extra={"studentProfile": default_student_profile()},
            )
        except ValueError as e:
            if str(e) == "EMAIL_EXISTS":
                return 409, error_body("EMAIL_EXISTS", "Email already registered.")
            raise
        status, payload = join_class_by_access_code(user["id"], access_code)
        if status != 200:
            delete_user(user["id"])
            return status, payload
        return 201, success_body({"user": public_user(user)})

    extra = {"publicProfile": {"location": "", "interestSpecies": []}} if parsed["role"] == "PUBLIC" else {"teacherClassIds": []}
    try:
        user = create_user(
            parsed["name"],
            parsed["email"],
            parsed["password"],
            parsed["role"],
            extra=extra,
        )
    except ValueError as e:
        if str(e) == "EMAIL_EXISTS":
            return 409, error_body("EMAIL_EXISTS", "Email already registered.")
        raise
    return 201, success_body({"user": public_user(user)})


def handle_login(body: dict, remote_addr: str = "unknown") -> tuple[int, dict, str | None]:
    seed_users_if_empty()
    err_code, parsed = validate_login(body)
    if err_code:
        if err_code == "INVALID_BODY":
            return 400, error_body("INVALID_BODY", "Request body must be JSON."), None
        return 400, error_body(err_code, parsed["message"], parsed), None
    try:
        rate_limit = login_rate_limit_service.check(parsed["email"], remote_addr)
    except Exception:
        return 503, error_body("SECURITY_CONFIGURATION_ERROR", "Login is temporarily unavailable."), None
    if not rate_limit.allowed:
        return 429, error_body("TOO_MANY_LOGIN_ATTEMPTS", "Too many unsuccessful attempts. Please try again later."), None

    user = find_by_email(parsed["email"])
    if not user or not verify_password(parsed["password"], user.get("passwordHash", "")):
        try:
            login_rate_limit_service.record_failure(parsed["email"], remote_addr)
        except Exception:
            return 503, error_body("SECURITY_CONFIGURATION_ERROR", "Login is temporarily unavailable."), None
        return 401, error_body("INVALID_CREDENTIALS", "Incorrect email or password."), None
    try:
        login_rate_limit_service.record_success(parsed["email"], remote_addr)
    except Exception:
        return 503, error_body("SECURITY_CONFIGURATION_ERROR", "Login is temporarily unavailable."), None
    token = create_session(user["id"])
    return 200, success_body({"user": public_user(user)}), token


def handle_logout(handler) -> tuple[int, dict, bool]:
    token = parse_session_token(handler)
    if token:
        delete_session(token)
    return 200, success_body({"message": "Signed out."}), True


def handle_change_password(handler, body: dict) -> tuple[int, dict, bool]:
    """Change the authenticated user's password and invalidate this session.

    This deliberately relies on the project's existing user repository and
    session deletion routine: it adds no table and stores no reset token.
    Removing the current session prevents a browser with an old cookie from
    continuing after the credential has changed.
    """
    user = get_current_user(handler)
    if not user:
        return 401, error_body("UNAUTHORIZED", "Authentication required."), False

    err_code, parsed = validate_change_password(body)
    if err_code:
        if err_code == "INVALID_BODY":
            return 400, error_body("INVALID_BODY", "Request body must be JSON."), False
        return 400, error_body(err_code, parsed["message"], parsed), False

    stored_user = find_by_id(user["id"])
    if not stored_user:
        return 401, error_body("UNAUTHORIZED", "Authentication required."), False
    if not verify_password(parsed["currentPassword"], stored_user.get("passwordHash", "")):
        # Do not reveal whether an account record has been changed elsewhere.
        return 401, error_body("INVALID_CREDENTIALS", "Current password is incorrect."), False

    token = parse_session_token(handler)
    if token:
        # Revoke before writing the credential. If session storage is briefly
        # unavailable, the old password remains valid and the request fails.
        delete_session(token)
    updated_user = update_user(user["id"], {"passwordHash": hash_password(parsed["newPassword"])})
    if not updated_user:
        return 404, error_body("USER_NOT_FOUND", "User account was not found."), True
    return 200, success_body({"message": "Password changed. Please sign in again."}), True


def handle_me(handler) -> tuple[int, dict]:
    user = get_current_user(handler)
    if not user:
        return 401, error_body("UNAUTHORIZED", "Not signed in.")
    return 200, success_body({"user": user})
