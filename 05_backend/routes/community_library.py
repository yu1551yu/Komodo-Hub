from __future__ import annotations

from api.errors import error_body, success_body
from services.community_library_service import community_library, community_public_profile, member_public_contributions, member_public_profile


def _run(callback):
    try:
        return 200, success_body(callback())
    except ValueError:
        return 404, error_body("NOT_FOUND", "Public community resource not found.")
    except Exception:
        return 500, error_body("DATA_ERROR", "Public community resource is unavailable.")


def library(organisation_id):
    return _run(lambda: community_library(organisation_id))


def community_profile(organisation_id):
    return _run(lambda: community_public_profile(organisation_id))


def member_profile(user_id):
    return _run(lambda: member_public_profile(user_id))


def member_contributions(user_id):
    return _run(lambda: member_public_contributions(user_id))
