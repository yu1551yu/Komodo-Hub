from auth.middleware import require_role
from services.account_profile_service import avatar_bytes, get_profile, patch_profile, upload_avatar


def _public(handler):
    user, err = require_role(handler, "PUBLIC")
    return user, ((401 if err["error"]["code"] == "UNAUTHORIZED" else 403), err) if err else None


def get(handler):
    user, failure = _public(handler)
    return failure or get_profile(user["id"], "PUBLIC")


def patch(handler, body):
    user, failure = _public(handler)
    return failure or patch_profile(user["id"], "PUBLIC", body)


def upload(handler, body):
    user, failure = _public(handler)
    return failure or upload_avatar(user["id"], "PUBLIC", body)


def image(handler):
    user, failure = _public(handler)
    if failure:
        return failure[0], None, None, failure[1]
    return avatar_bytes(user["id"], "PUBLIC")
