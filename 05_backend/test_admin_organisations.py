from __future__ import annotations

import unittest

from models.json_store import DATA_DIR, write_rows
from services.admin_organisation_service import change_administrator, create, detail, list_all, set_status, stats, update, user_search
from services.organisation_admin_invitation_service import mine, respond

FILES = ["users.json", "community_organisations.json", "community_memberships.json", "program_enrollments.json", "community_contributions.json", "species_sightings.json", "admin_audit_log.json", "organisation_admin_invitations.json", "notifications.json"]


class AdminOrganisationTest(unittest.TestCase):
    def setUp(self):
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).is_file() else None for name in FILES}
        write_rows("users.json", [
            {"id": "super1", "name": "Super", "email": "super@test", "role": "ADMIN"},
            {"id": "public1", "name": "First Admin", "email": "first@test", "role": "PUBLIC"},
            {"id": "public2", "name": "Second Admin", "email": "second@test", "role": "PUBLIC"},
        ])
        write_rows("community_organisations.json", [])
        write_rows("community_memberships.json", [])
        write_rows("program_enrollments.json", [])
        write_rows("community_contributions.json", [])
        write_rows("species_sightings.json", [])
        write_rows("admin_audit_log.json", [])
        write_rows("organisation_admin_invitations.json", [])
        write_rows("notifications.json", [])
        self.actor = {"id": "super1", "role": "ADMIN"}

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None: path.unlink(missing_ok=True)
            else: path.write_bytes(data)

    def test_super_admin_end_to_end_organization_flow(self):
        created = create(self.actor, {"name": "Forest Group", "description": "Protect forests", "location": "Java", "administratorUserId": "public1"})["organisation"]
        self.assertIsNone(created["administrator"])
        invitation = mine({"id": "public1", "role": "PUBLIC"})["invitations"][0]
        accepted = respond({"id": "public1", "role": "PUBLIC"}, invitation["id"], "ACCEPTED")
        self.assertEqual(accepted["membership"]["role"], "OWNER")
        self.assertEqual(list_all(self.actor)["total"], 1)
        updated = update(self.actor, created["id"], {"name": "Forest Guardians", "location": "West Java"})["organisation"]
        self.assertEqual(updated["name"], "Forest Guardians")
        pending = change_administrator(self.actor, created["id"], "public2")
        self.assertEqual(pending["invitation"]["status"], "PENDING")
        self.assertEqual(pending["administrator"]["id"], "public1")
        changed_invite = mine({"id": "public2", "role": "PUBLIC"})["invitations"][0]
        respond({"id": "public2", "role": "PUBLIC"}, changed_invite["id"], "ACCEPTED")
        members = detail(self.actor, created["id"])["members"]
        self.assertEqual(sum(row["role"] == "OWNER" for row in members), 1)
        self.assertEqual(next(row for row in members if row["userId"] == "public1")["role"], "MEMBER")
        disabled = set_status(self.actor, created["id"], "INACTIVE")["organisation"]
        self.assertEqual(disabled["status"], "inactive")
        self.assertEqual(stats(self.actor)["inactive"], 1)

    def test_invitation_cannot_be_accepted_by_another_user(self):
        result = create(self.actor, {"name": "Secure Group", "administratorUserId": "public1"})
        invitation = result["invitation"]
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            respond({"id": "public2", "role": "PUBLIC"}, invitation["id"], "ACCEPTED")
        self.assertEqual(detail(self.actor, result["organisation"]["id"])["members"], [])

    def test_non_admin_is_forbidden_and_invalid_admin_rolls_back(self):
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            list_all({"id": "public1", "role": "PUBLIC"})
        with self.assertRaisesRegex(ValueError, "ADMIN_USER_NOT_FOUND"):
            create(self.actor, {"name": "Broken Group", "administratorUserId": "missing"})
        self.assertEqual(list_all(self.actor)["total"], 0)

    def test_search_returns_only_minimal_public_user_fields(self):
        result = user_search(self.actor, "first")["users"][0]
        self.assertEqual(set(result), {"id", "name", "email"})


if __name__ == "__main__":
    unittest.main()
