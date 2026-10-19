from __future__ import annotations

import unittest
from models.json_store import DATA_DIR, write_rows
import base64
from services.community_portal_service import COVER_DIR, remove_organisation_cover, update_organisation_profile, upload_organisation_cover


class OrganisationAdminPortalTest(unittest.TestCase):
    def setUp(self):
        self.files = ["community_organisations.json", "community_memberships.json", "users.json"]
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).exists() else None for name in self.files}
        write_rows("users.json", [{"id": "admin1", "role": "PUBLIC", "name": "Admin"}, {"id": "member1", "role": "PUBLIC", "name": "Member"}])
        write_rows("community_organisations.json", [{"id": "org1", "name": "Original", "bio": "Old", "region": "Bali", "status": "approved"}])
        write_rows("community_memberships.json", [{"id": "m1", "organisationId": "org1", "userId": "admin1", "role": "OWNER", "status": "active"}, {"id": "m2", "organisationId": "org1", "userId": "member1", "role": "MEMBER", "status": "active"}])

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None: path.unlink(missing_ok=True)
            else: path.write_bytes(data)
        for suffix in (".jpg", ".png", ".webp"):
            (COVER_DIR / f"org1{suffix}").unlink(missing_ok=True)

    def test_admin_can_update_own_organization_profile(self):
        result = update_organisation_profile({"id": "admin1", "role": "PUBLIC"}, "org1", {"name": "Updated", "website": "https://example.org"})
        self.assertEqual(result["organisation"]["name"], "Updated")
        self.assertEqual(result["organisation"]["website"], "https://example.org")

    def test_member_cannot_update_organization_profile(self):
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            update_organisation_profile({"id": "member1", "role": "PUBLIC"}, "org1", {"name": "Nope"})

    def test_admin_can_upload_and_restore_default_cover(self):
        image = base64.b64encode(b"valid-test-image").decode()
        uploaded = upload_organisation_cover({"id": "admin1", "role": "PUBLIC"}, "org1", {"contentType": "image/png", "imageBase64": image})
        self.assertIn("/cover?v=img_", uploaded["coverImageUrl"])
        self.assertTrue((COVER_DIR / "org1.png").is_file())
        restored = remove_organisation_cover({"id": "admin1", "role": "PUBLIC"}, "org1")
        self.assertIsNone(restored["coverImageUrl"])
        self.assertNotIn("coverImageUrl", restored["organisation"])
        self.assertFalse((COVER_DIR / "org1.png").exists())

    def test_member_cannot_remove_cover(self):
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            remove_organisation_cover({"id": "member1", "role": "PUBLIC"}, "org1")


if __name__ == "__main__":
    unittest.main()
