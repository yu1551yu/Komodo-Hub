from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import get_current_user, require_auth
from services.community_portal_service import (
    add_member,
    change_member_role,
    create_community,
    decide_join_request,
    join_requests,
    join_organisation,
    member_candidates,
    my_communities,
    organisation_members,
    organisation_workspace,
    public_directory,
    remove_member,
    update_organisation_profile,
    upload_organisation_cover,
    organisation_cover,
    remove_organisation_cover,
)


def _error(exc):
    code = str(exc)
    if code == "FORBIDDEN":
        return 403, error_body("FORBIDDEN", "You do not have permission for this community.")
    if code == "NOT_FOUND":
        return 404, error_body("NOT_FOUND", "Community organisation not found.")
    if code == "ADMIN_USER_NOT_FOUND":
        return 400, error_body("VALIDATION_ERROR", "The nominated community admin user does not exist.")
    if code == "PASSWORD_REQUIRED":
        return 400, error_body("VALIDATION_ERROR", "A password of at least 6 characters is required for a new member account.")
    if code in {"DUPLICATE_REQUEST", "ALREADY_MEMBER", "ALREADY_REVIEWED"}:
        return 409, error_body("CONFLICT", "This membership request has already been submitted or resolved.")
    return 400, error_body("VALIDATION_ERROR", "Invalid community portal request.")


def directory(handler):
    return 200, success_body(public_directory(get_current_user(handler)))


def create(handler, body):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 201, success_body(create_community(actor, body))
    except ValueError as exc:
        return _error(exc)


def join(handler, organisation_id, body=None):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 201, success_body(join_organisation(actor, organisation_id, body))
    except ValueError as exc:
        return _error(exc)


def workspace(handler, organisation_id):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 200, success_body(organisation_workspace(actor, organisation_id))
    except ValueError as exc:
        return _error(exc)


def workspace_update(handler, organisation_id, body):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(update_organisation_profile(actor, organisation_id, body))
    except ValueError as exc: return _error(exc)


def cover_upload(handler, organisation_id, body):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(upload_organisation_cover(actor, organisation_id, body))
    except ValueError as exc: return _error(exc)
    except Exception: return 500, error_body("DATA_ERROR", "Organization cover could not be saved.")


def cover_remove(handler, organisation_id):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(remove_organisation_cover(actor, organisation_id))
    except ValueError as exc: return _error(exc)
    except Exception: return 500, error_body("DATA_ERROR", "Organization cover could not be restored.")


def cover_image(organisation_id):
    data, content_type = organisation_cover(organisation_id)
    if not data: return 404, None, None, error_body("NOT_FOUND", "Organization cover not found.")
    return 200, data, content_type, None


def members(handler, organisation_id):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 200, success_body(organisation_members(actor, organisation_id))
    except ValueError as exc:
        return _error(exc)


def member_create(handler, organisation_id, body):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 201, success_body(add_member(actor, organisation_id, body))
    except ValueError as exc:
        return _error(exc)


def member_role(handler, membership_id, body):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        role = str(body.get("role") or "").upper()
        return 200, success_body(change_member_role(actor, membership_id, role))
    except ValueError as exc:
        return _error(exc)


def member_delete(handler, membership_id):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 200, success_body(remove_member(actor, membership_id))
    except ValueError as exc:
        return _error(exc)


def mine(handler):
    actor, err = require_auth(handler)
    if err: return 401, err
    return 200, success_body(my_communities(actor))


def requests(handler, organisation_id):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(join_requests(actor, organisation_id))
    except ValueError as exc: return _error(exc)


def request_decision(handler, request_id, body):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(decide_join_request(actor, request_id, str(body.get("status") or "").lower()))
    except ValueError as exc: return _error(exc)


def candidates(handler, organisation_id, query):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(member_candidates(actor, organisation_id, query))
    except ValueError as exc: return _error(exc)
