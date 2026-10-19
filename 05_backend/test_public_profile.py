from __future__ import annotations

import unittest

from models.json_store import DATA_DIR, write_rows
from services.account_profile_service import get_profile, patch_profile


class PublicProfileTest(unittest.TestCase):
    def setUp(self):
        self.path = DATA_DIR / "users.json"
        self.backup = self.path.read_bytes() if self.path.is_file() else None
        write_rows("users.json", [
            {"id": "public1", "name": "Public User", "email": "public@example.test", "role": "PUBLIC"},
            {"id": "student1", "name": "Student User", "email": "student@example.test", "role": "STUDENT"},
        ])

    def tearDown(self):
        if self.backup is None:
            self.path.unlink(missing_ok=True)
        else:
            self.path.write_bytes(self.backup)

    def test_public_profile_uses_shared_profile_shape(self):
        status, body = get_profile("public1", "PUBLIC")
        self.assertEqual(status, 200)
        profile = body["data"]["profile"]
        self.assertEqual(profile["role"], "PUBLIC")
        self.assertEqual(profile["realName"], "Public User")
        self.assertIn("backgroundOptions", profile)
        self.assertIn("avatarId", profile)

    def test_public_profile_can_be_updated_without_changing_identity(self):
        status, body = patch_profile("public1", "PUBLIC", {"nickname": "Observer", "signature": "Coastal volunteer"})
        self.assertEqual(status, 200)
        profile = body["data"]["profile"]
        self.assertEqual(profile["displayName"], "Observer")
        self.assertEqual(profile["realName"], "Public User")
        denied, _ = get_profile("student1", "PUBLIC")
        self.assertEqual(denied, 403)


if __name__ == "__main__":
    unittest.main()
