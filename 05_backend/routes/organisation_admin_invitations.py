from api.errors import error_body, success_body
from auth.middleware import require_auth
from services.organisation_admin_invitation_service import mine, respond


def _error(exc):
    code = str(exc)
    status = 403 if code == "FORBIDDEN" else 404 if code == "NOT_FOUND" else 409 if code == "ALREADY_REVIEWED" else 400
    return status, error_body(code, "Organization administrator invitation operation failed.")


def index(handler):
    actor, err = require_auth(handler)
    if err: return 401, err
    return 200, success_body(mine(actor))


def decision(handler, invitation_id, body):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(respond(actor, invitation_id, str(body.get("decision") or "")))
    except ValueError as exc: return _error(exc)
