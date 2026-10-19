from api.errors import error_body, success_body
from auth.middleware import require_auth
from services import admin_organisation_service as service


def _run(handler, action, success=200):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return success, success_body(action(actor))
    except ValueError as exc:
        code = str(exc)
        status = 403 if code == "FORBIDDEN" else 404 if code == "NOT_FOUND" else 409 if code == "DUPLICATE_ORGANISATION" else 400
        return status, error_body(code, "Organization management operation failed.")
    except Exception:
        return 500, error_body("DATA_ERROR", "Organization management data is unavailable.")


def index(handler, query="", status=""): return _run(handler, lambda actor: service.list_all(actor, query, status))
def statistics(handler): return _run(handler, service.stats)
def detail(handler, organisation_id): return _run(handler, lambda actor: service.detail(actor, organisation_id))
def create(handler, body): return _run(handler, lambda actor: service.create(actor, body), 201)
def update(handler, organisation_id, body): return _run(handler, lambda actor: service.update(actor, organisation_id, body))
def status(handler, organisation_id, body): return _run(handler, lambda actor: service.set_status(actor, organisation_id, str(body.get("status") or "")))
def administrator(handler, organisation_id, body): return _run(handler, lambda actor: service.change_administrator(actor, organisation_id, str(body.get("newAdministratorUserId") or "")))
def users(handler, query): return _run(handler, lambda actor: service.user_search(actor, query))
