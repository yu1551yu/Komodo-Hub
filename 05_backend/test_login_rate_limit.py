from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


class LoginRateLimitServiceTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"LOGIN_RATE_LIMIT_PEPPER": "x" * 32})
        self.env.start()
        from services import login_rate_limit_service as service
        self.service = service
        self.store = service.InMemoryLoginRateLimitStore()

    def tearDown(self):
        self.env.stop()

    def test_missing_configuration_generates_a_safe_process_local_pepper(self):
        generated = self.service._resolve_pepper("")
        self.assertGreaterEqual(len(generated), 32)
        self.assertNotEqual(generated, self.service._resolve_pepper("x" * 31))

    def test_five_failures_create_a_lock(self):
        for _ in range(4):
            self.assertTrue(self.service.record_failure("student@example.test", "192.0.2.10", self.store).allowed)
        fifth = self.service.record_failure("student@example.test", "192.0.2.10", self.store)
        self.assertFalse(fifth.allowed)
        self.assertEqual(fifth.retry_after_seconds, 300)
        self.assertFalse(self.service.check("student@example.test", "192.0.2.10", self.store).allowed)

    def test_success_clears_only_its_matching_attempt_state(self):
        self.service.record_failure("one@example.test", "192.0.2.10", self.store)
        self.service.record_failure("two@example.test", "192.0.2.10", self.store)
        self.service.record_success("one@example.test", "192.0.2.10", self.store)
        self.assertTrue(self.service.check("one@example.test", "192.0.2.10", self.store).allowed)
        ip_fingerprint = self.service._fingerprints("two@example.test", "192.0.2.10")[1]
        self.assertIsNotNone(self.store.get_attempt("IP", ip_fingerprint))

    def test_expired_lock_is_removed_before_the_next_attempt(self):
        email_key, _ = self.service._fingerprints("student@example.test", "192.0.2.10")
        self.store._rows[("ACCOUNT", email_key)] = self.service.AttemptState(5, datetime.now(timezone.utc) - timedelta(seconds=1))
        self.assertTrue(self.service.check("student@example.test", "192.0.2.10", self.store).allowed)
        self.assertIsNone(self.store.get_attempt("ACCOUNT", email_key))

    def test_rotating_ip_addresses_cannot_bypass_an_account_lock(self):
        for octet in range(1, 6):
            self.service.record_failure("student@example.test", f"192.0.2.{octet}", self.store)
        self.assertFalse(self.service.check("student@example.test", "198.51.100.9", self.store).allowed)

    def test_ip_wide_limit_blocks_password_spraying_after_twenty_attempts(self):
        for number in range(20):
            self.service.record_failure(f"student{number}@example.test", "192.0.2.10", self.store)
        self.assertFalse(self.service.check("new-student@example.test", "192.0.2.10", self.store).allowed)


class LoginHandlerIntegrationTest(unittest.TestCase):
    def setUp(self):
        from auth import handlers
        from services.login_rate_limit_service import RateLimitResult

        self.handlers = handlers
        self.allowed = RateLimitResult(True)

    def test_unknown_email_and_wrong_password_have_the_same_response(self):
        body = {"email": "student@example.test", "password": "wrong"}
        with patch.object(self.handlers, "seed_users_if_empty"), \
             patch.object(self.handlers.login_rate_limit_service, "check", return_value=self.allowed), \
             patch.object(self.handlers.login_rate_limit_service, "record_failure"):
            with patch.object(self.handlers, "find_by_email", return_value=None):
                unknown = self.handlers.handle_login(body, "192.0.2.10")
            with patch.object(self.handlers, "find_by_email", return_value={"passwordHash": "hash"}), \
                 patch.object(self.handlers, "verify_password", return_value=False):
                wrong_password = self.handlers.handle_login(body, "192.0.2.10")
        self.assertEqual(unknown[0], 401)
        self.assertEqual(unknown[1], wrong_password[1])

    def test_locked_login_does_not_attempt_user_lookup(self):
        from services.login_rate_limit_service import RateLimitResult

        with patch.object(self.handlers, "seed_users_if_empty"), \
             patch.object(self.handlers.login_rate_limit_service, "check", return_value=RateLimitResult(False, 300)), \
             patch.object(self.handlers, "find_by_email") as find_user:
            status, body, token = self.handlers.handle_login({"email": "student@example.test", "password": "wrong"}, "192.0.2.10")
        self.assertEqual(status, 429)
        self.assertEqual(body["error"]["code"], "TOO_MANY_LOGIN_ATTEMPTS")
        self.assertIsNone(token)
        find_user.assert_not_called()

    def test_successful_login_clears_the_matching_rate_limit_state(self):
        user = {"id": "student-1", "passwordHash": "hash"}
        with patch.object(self.handlers, "seed_users_if_empty"), \
             patch.object(self.handlers.login_rate_limit_service, "check", return_value=self.allowed), \
             patch.object(self.handlers, "find_by_email", return_value=user), \
             patch.object(self.handlers, "verify_password", return_value=True), \
             patch.object(self.handlers.login_rate_limit_service, "record_success") as clear_attempts, \
             patch.object(self.handlers, "create_session", return_value="session-token"), \
             patch.object(self.handlers, "public_user", return_value={"id": "student-1"}):
            status, _, token = self.handlers.handle_login({"email": "student@example.test", "password": "right"}, "192.0.2.10")
        self.assertEqual(status, 200)
        self.assertEqual(token, "session-token")
        clear_attempts.assert_called_once_with("student@example.test", "192.0.2.10")


if __name__ == "__main__":
    unittest.main()
