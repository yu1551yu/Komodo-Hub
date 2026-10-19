from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import require_auth
from services.contribution_service import add_comment, contribution_comments, contribution_detail, create, my_contributions, public_contributions, read_comment, received_comments


def _error(exc):
    code = str(exc)
    if code == "FORBIDDEN":
        return 403, error_body("FORBIDDEN", "You cannot publish for this community.")
    if code == "NOT_FOUND":
        return 404, error_body("NOT_FOUND", "Contribution not found.")
    if code == "INVALID_ID":
        return 400, error_body("VALIDATION_ERROR", "Invalid contribution id.")
    return 400, error_body("VALIDATION_ERROR", "Invalid contribution content.")


def index(query: dict | None = None):
    try:
        organisation_id = (query or {}).get("organisationId")
        return 200, success_body(public_contributions(organisation_id))
    except Exception:
        return 500, error_body("DATA_ERROR", "Community contributions are unavailable.")


def detail(contribution_id: str):
    try:
        return 200, success_body(contribution_detail(contribution_id))
    except ValueError as exc:
        return _error(exc)
    except Exception:
        return 500, error_body("DATA_ERROR", "Community contribution is unavailable.")


def mine(handler):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    return 200, success_body(my_contributions(actor))


def post(handler, body):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 201, success_body(create(actor, body))
    except ValueError as exc:
        return _error(exc)


def comments(contribution_id: str):
    try:
        return 200, success_body(contribution_comments(contribution_id))
    except ValueError as exc:
        return _error(exc)


def comment(handler, contribution_id: str, body: dict):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 201, success_body(add_comment(actor, contribution_id, body))
    except ValueError as exc:
        return _error(exc)


def received(handler):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    return 200, success_body(received_comments(actor))


def read(handler, comment_id: str):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 200, success_body(read_comment(actor, comment_id))
    except ValueError as exc:
        return _error(exc)
