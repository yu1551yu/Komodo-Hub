from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import require_role
from services.creative_canvas_service import add_items, candidates, canvas_item, my_canvas, remove_item, reorder


def _actor(handler):
    actor, err = require_role(handler, "PUBLIC")
    if err:
        return None, (401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err)
    return actor, None


def _run(handler, action, status=200):
    actor, failure = _actor(handler)
    if failure:
        return failure
    try:
        return status, success_body(action(actor["id"]))
    except ValueError as exc:
        code = str(exc)
        if code == "NOT_FOUND":
            return 404, error_body("NOT_FOUND", "Canvas item or source work not found.")
        return 400, error_body("VALIDATION_ERROR", "Invalid Creative Canvas request.", {"reason": code})
    except Exception:
        return 500, error_body("DATA_ERROR", "Creative Canvas is unavailable.")


def index(handler):
    return _run(handler, my_canvas)


def candidate_list(handler):
    return _run(handler, candidates)


def detail(handler, item_id):
    return _run(handler, lambda owner_id: canvas_item(owner_id, item_id))


def post(handler, body):
    return _run(handler, lambda owner_id: add_items(owner_id, body), 201)


def delete(handler, item_id):
    return _run(handler, lambda owner_id: remove_item(owner_id, item_id))


def order(handler, body):
    return _run(handler, lambda owner_id: reorder(owner_id, body))
