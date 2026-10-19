from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.handlers import handle_change_password
from auth.passwords import hash_password, verify_password
from api.validation import validate_change_password


class PasswordChangeTests(unittest.TestCase):
    def setUp(self):
        self.handler = object()
        self.user = {
            "id": "usr_test",
            "email": "test@example.com",
            "name": "Test User",
            "role": "STUDENT",
            "passwordHash": hash_password("old-password-123"),
        }

    def test_validation_requires_a_longer_different_new_password(self):
        self.assertEqual(validate_change_password({"currentPassword": "a", "newPassword": "short"})[0], "VALIDATION_ERROR")
        self.assertEqual(validate_change_password({"currentPassword": "same-password", "newPassword": "same-password"})[0], "VALIDATION_ERROR")

    @patch("auth.handlers.update_user")
    @patch("auth.handlers.delete_session")
    @patch("auth.handlers.parse_session_token", return_value="session-token")
    @patch("auth.handlers.find_by_id")
    @patch("auth.handlers.get_current_user")
    def test_success_updates_hash_and_revokes_current_session(self, get_current, find_user, token, delete, update):
        get_current.return_value = {key: self.user[key] for key in ("id", "email", "name", "role")}
        find_user.return_value = self.user
        update.return_value = self.user

        status, payload, clear = handle_change_password(self.handler, {
            "currentPassword": "old-password-123", "newPassword": "new-password-456"
        })

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(clear)
        delete.assert_called_once_with("session-token")
        patch_value = update.call_args.args[1]["passwordHash"]
        self.assertTrue(verify_password("new-password-456", patch_value))

    @patch("auth.handlers.update_user")
    @patch("auth.handlers.delete_session")
    @patch("auth.handlers.find_by_id")
    @patch("auth.handlers.get_current_user")
    def test_wrong_current_password_does_not_change_or_revoke(self, get_current, find_user, delete, update):
        get_current.return_value = {key: self.user[key] for key in ("id", "email", "name", "role")}
        find_user.return_value = self.user

        status, payload, clear = handle_change_password(self.handler, {
            "currentPassword": "not-the-password", "newPassword": "new-password-456"
        })

        self.assertEqual(status, 401)
        self.assertEqual(payload["error"]["code"], "INVALID_CREDENTIALS")
        self.assertFalse(clear)
        delete.assert_not_called()
        update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
