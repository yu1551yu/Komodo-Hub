from auth.middleware import require_role
from services.account_profile_service import avatar_bytes, get_profile, patch_profile, upload_avatar


def _teacher(handler):
    user, err = require_role(handler, "TEACHER")
    return user, ((401 if err["error"]["code"] == "UNAUTHORIZED" else 403), err) if err else None


def get(handler):
    user, failure = _teacher(handler); return failure or get_profile(user["id"], "TEACHER")
def patch(handler, body):
    user, failure = _teacher(handler); return failure or patch_profile(user["id"], "TEACHER", body)
def upload(handler, body):
    user, failure = _teacher(handler); return failure or upload_avatar(user["id"], "TEACHER", body)
def image(handler):
    user, failure = _teacher(handler)
    if failure: return failure[0], None, None, failure[1]
    return avatar_bytes(user["id"], "TEACHER")
