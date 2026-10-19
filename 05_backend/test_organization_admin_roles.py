from __future__ import annotations

import unittest
from models.json_store import DATA_DIR, write_rows
from models.community_repository import deactivate_membership, update_membership_role


class OrganizationAdminRolesTest(unittest.TestCase):
    def setUp(self):
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).exists() else None for name in ["community_organisations.json", "community_memberships.json"]}
        write_rows("community_organisations.json", [{"id": "org1", "name": "Org", "status": "approved"}])
        write_rows("community_memberships.json", [
            {"id": "owner", "organisationId": "org1", "userId": "u1", "role": "OWNER", "status": "active"},
            {"id": "deputy", "organisationId": "org1", "userId": "u2", "role": "ADMIN", "status": "active"},
            {"id": "member", "organisationId": "org1", "userId": "u3", "role": "MEMBER", "status": "active"},
        ])

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None: path.unlink(missing_ok=True)
            else: path.write_bytes(data)

    def test_owner_can_appoint_deputy(self):
        self.assertEqual(update_membership_role("u1", "member", "ADMIN")["role"], "ADMIN")

    def test_deputy_cannot_appoint_or_remove_peer_but_can_remove_member(self):
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            update_membership_role("u2", "member", "ADMIN")
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            deactivate_membership("u2", "owner")
        self.assertEqual(deactivate_membership("u2", "member")["status"], "inactive")


if __name__ == "__main__": unittest.main()
