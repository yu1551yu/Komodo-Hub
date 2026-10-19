"""Smoke tests for student profile API."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from auth.handlers import handle_login
from auth.sessions import COOKIE_NAME
from models.user_repository import seed_users_if_empty
from routes.student import handle_my_profile, handle_patch_my_profile, handle_upload_avatar


class MockHandler:
    def __init__(self, cookie: str | None = None):
        self.headers = {}
        if cookie:
            self.headers["Cookie"] = f"{COOKIE_NAME}={cookie}"


def main() -> None:
    seed_users_if_empty()

    status, _ = handle_my_profile(MockHandler())
    assert status == 401, status

    s, _, token = handle_login({"email": "teacher@komodo.id", "password": "demo123"})
    assert s == 200 and token
    status, body = handle_my_profile(MockHandler(token))
    assert status == 403, (status, body)

    s, _, token = handle_login({"email": "student@komodo.id", "password": "demo123"})
    assert s == 200 and token
    h = MockHandler(token)

    status, body = handle_my_profile(h)
    assert status == 200, body
    assert body["data"]["profile"]["displayName"]
    assert "backgroundOptions" in body["data"]["profile"]
    assert len(body["data"]["profile"]["backgroundOptions"]) == 4

    status, body = handle_patch_my_profile(
        h, {"displayName": "Rafi M.", "role": "TEACHER", "id": "hacked"}
    )
    assert status == 400, (status, body)
    assert "fields" in body["error"].get("details", {}) or "displayName" in body["error"]["message"]

    status, body = handle_patch_my_profile(h, {"themeColor": "#000000"})
    assert status == 400, body

    status, body = handle_patch_my_profile(
        h,
        {
            "nickname": "RafiNick",
            "signature": "Protect the forest.",
            "gender": "M",
            "avatarId": "avatar-owl",
            "profileBg": "ocean",
        },
    )
    assert status == 200, body
    prof = body["data"]["profile"]
    assert prof["nickname"] == "RafiNick"
    assert prof["displayName"] == "RafiNick"
    assert prof["signature"] == "Protect the forest."
    assert prof["gender"] == "M"
    assert prof["avatarId"] == "avatar-owl"
    assert prof["profileBg"] == "ocean"
    assert prof["themeColor"].lower() == "#2563eb"
    assert prof["role"] == "STUDENT"

    status, body = handle_my_profile(h)
    assert body["data"]["profile"]["displayName"] == "RafiNick"

    status, body = handle_patch_my_profile(h, {"avatarId": "not-a-preset"})
    assert status == 400, body

    # Minimal valid PNG (1x1)
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    status, body = handle_upload_avatar(
        h, {"imageBase64": png_b64, "contentType": "image/png"}
    )
    assert status == 200, body
    assert body["data"]["profile"]["avatarType"] == "upload"
    assert body["data"]["profile"]["avatarUrl"] == "/api/students/me/avatar"

    print("student profile smoke tests passed")


if __name__ == "__main__":
    main()
