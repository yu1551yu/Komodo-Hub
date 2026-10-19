from api.errors import error_body, success_body
from auth.middleware import require_auth
from services.contribution_review_service import review, review_queue


def _error(exc):
    code = str(exc)
    status = 403 if code == "FORBIDDEN" else 404 if code == "NOT_FOUND" else 400
    return status, error_body(code, "Contribution review operation failed.")


def index(handler, organisation_id):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(review_queue(actor, organisation_id))
    except ValueError as exc: return _error(exc)


def decision(handler, organisation_id, resource_type, resource_id, body):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(review(actor, organisation_id, resource_type, resource_id, str(body.get("decision") or ""), str(body.get("reason") or "")))
    except ValueError as exc: return _error(exc)
