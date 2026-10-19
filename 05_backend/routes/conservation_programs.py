from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import get_current_user, require_auth
from services.conservation_program_service import (
    assign_member,
    assign_members,
    community_program_context,
    enroll_self,
    my_enrollments,
    program_detail,
    public_programs,
    save_community_program,
    apply_to_program,
    organisation_program_applications,
    review_program_application,
)


def _error(exc):
    code = str(exc)
    if code == "FORBIDDEN":
        return 403, error_body("FORBIDDEN", "You do not have permission for this program action.")
    if code == "NOT_FOUND":
        return 404, error_body("NOT_FOUND", "Conservation program not found.")
    if code == "ALREADY_JOINED":
        return 409, error_body("ALREADY_JOINED", "You have already joined this program through this organization.")
    if code == "INVALID_ID":
        return 400, error_body("VALIDATION_ERROR", "Invalid program id.")
    return 400, error_body("VALIDATION_ERROR", "Invalid program enrollment request.")


def index(handler):
    try:
        return 200, success_body(public_programs(get_current_user(handler)))
    except Exception:
        return 500, error_body("DATA_ERROR", "Conservation programs are unavailable.")


def detail(handler, program_id):
    try:
        return 200, success_body(program_detail(program_id, get_current_user(handler)))
    except ValueError as exc:
        return _error(exc)
    except Exception:
        return 500, error_body("DATA_ERROR", "Conservation program is unavailable.")


def me(handler):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 200, success_body(my_enrollments(actor))
    except Exception:
        return 500, error_body("DATA_ERROR", "Program enrollments are unavailable.")


def self_enroll(handler, program_id):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 201, success_body(enroll_self(actor, program_id))
    except ValueError as exc:
        return _error(exc)
    except Exception:
        return 500, error_body("DATA_ERROR", "Program enrollment could not be saved.")


def community_context(handler, organisation_id):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 200, success_body(community_program_context(actor, organisation_id))
    except ValueError as exc:
        return _error(exc)
    except Exception:
        return 500, error_body("DATA_ERROR", "Community program data is unavailable.")


def community_assign(handler, organisation_id, body):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        result = assign_members(actor, organisation_id, body) if isinstance(body.get("userIds"), list) else assign_member(actor, organisation_id, body)
        return 201, success_body(result)
    except ValueError as exc:
        return _error(exc)
    except Exception:
        return 500, error_body("DATA_ERROR", "Program assignment could not be saved.")


def community_program_save(handler, organisation_id, body, program_id=None):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return (200 if program_id else 201), success_body(save_community_program(actor, organisation_id, body, program_id))
    except ValueError as exc: return _error(exc)
    except Exception: return 500, error_body("DATA_ERROR", "Conservation program could not be saved.")


def apply(handler, program_id, body):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 201, success_body(apply_to_program(actor, program_id, body))
    except ValueError as exc: return _error(exc)
    except Exception: return 500, error_body("DATA_ERROR", "Program application could not be saved.")


def applications(handler, organisation_id):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(organisation_program_applications(actor, organisation_id))
    except ValueError as exc: return _error(exc)
    except Exception: return 500, error_body("DATA_ERROR", "Program applications are unavailable.")


def review_application(handler, organisation_id, application_id, body):
    actor, err = require_auth(handler)
    if err: return 401, err
    try: return 200, success_body(review_program_application(actor, organisation_id, application_id, body))
    except ValueError as exc: return _error(exc)
    except Exception: return 500, error_body("DATA_ERROR", "Program application decision could not be saved.")
