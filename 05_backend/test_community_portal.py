from __future__ import annotations

import unittest

from models.json_store import DATA_DIR, write_rows
from services.community_portal_service import (
    add_member,
    change_member_role,
    create_community,
    decide_join_request,
    join_organisation,
    join_requests,
    member_candidates,
    organisation_workspace,
    public_directory,
)
from models.community_repository import members_for_org

FILES = ["users.json", "community_organisations.json", "community_memberships.json", "community_join_requests.json"]


class CommunityPortalTest(unittest.TestCase):
    def setUp(self):
        self.backup = {
            name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).is_file() else None
            for name in FILES
        }
        write_rows(
            "users.json",
            [
                {"id": "admin1", "name": "Admin One", "email": "a@example.test", "role": "PUBLIC"},
                {"id": "member1", "name": "Member One", "email": "m@example.test", "role": "PUBLIC"},
                {"id": "outsider1", "name": "Outsider", "email": "o@example.test", "role": "PUBLIC"},
                {"id": "student1", "name": "School Student", "email": "s@example.test", "role": "STUDENT"},
            ],
        )
        write_rows(
            "community_organisations.json",
            [{"id": "org1", "name": "Org One", "bio": "Community group", "region": "Flores", "status": "approved"}],
        )
        write_rows(
            "community_memberships.json",
            [
                {"id": "mem1", "organisationId": "org1", "userId": "admin1", "role": "OWNER", "status": "active"},
                {"id": "mem2", "organisationId": "org1", "userId": "member1", "role": "MEMBER", "status": "active"},
            ],
        )
        write_rows("community_join_requests.json", [])

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)

    def test_guest_and_member_directory_states(self):
        guest = public_directory()
        self.assertEqual(guest["organisations"][0]["canJoin"], False)
        member = public_directory({"id": "member1", "role": "PUBLIC"})
        self.assertEqual(member["organisations"][0]["viewerMembership"]["role"], "MEMBER")
        self.assertEqual(member["organisations"][0]["canJoin"], False)

    def test_membership_controls_workspace_access(self):
        with self.assertRaises(ValueError):
            organisation_workspace({"id": "outsider1", "role": "PUBLIC"}, "org1")
        workspace = organisation_workspace({"id": "member1", "role": "PUBLIC"}, "org1")
        self.assertEqual(workspace["permissions"]["canManageMembers"], False)
        self.assertEqual(len(workspace["members"]), 2)

    def test_join_request_requires_admin_approval(self):
        submitted = join_organisation({"id": "outsider1", "role": "PUBLIC"}, "org1", {"note": "I help with coastal surveys."})
        self.assertEqual(submitted["joinRequest"]["status"], "pending")
        self.assertIsNone(next((row for row in members_for_org("org1") if row["userId"] == "outsider1"), None))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REQUEST"):
            join_organisation({"id": "outsider1", "role": "PUBLIC"}, "org1")
        approved = decide_join_request({"id": "admin1", "role": "PUBLIC"}, submitted["joinRequest"]["id"], "approved")
        self.assertEqual(approved["membership"]["role"], "MEMBER")
        updated = change_member_role({"id": "admin1", "role": "PUBLIC"}, approved["membership"]["id"], "ADMIN")
        self.assertEqual(updated["membership"]["role"], "ADMIN")

    def test_student_cannot_join_or_be_added_to_organization(self):
        student = {"id": "student1", "role": "STUDENT"}
        self.assertFalse(public_directory(student)["organisations"][0]["canJoin"])
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            join_organisation(student, "org1", {"note": "School identity"})
        with self.assertRaises(ValueError):
            add_member({"id": "admin1", "role": "PUBLIC"}, "org1", {"userId": "student1"})
        self.assertNotIn("student1", [row["id"] for row in member_candidates({"id": "admin1", "role": "PUBLIC"}, "org1", "School")["users"]])

    def test_member_cannot_review_and_rejection_does_not_join(self):
        request = join_organisation({"id": "outsider1", "role": "PUBLIC"}, "org1")["joinRequest"]
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            decide_join_request({"id": "member1", "role": "PUBLIC"}, request["id"], "approved")
        rejected = decide_join_request({"id": "admin1", "role": "PUBLIC"}, request["id"], "rejected")
        self.assertEqual(rejected["joinRequest"]["status"], "rejected")
        self.assertIsNone(rejected["membership"])
        directory = public_directory({"id": "outsider1", "role": "PUBLIC"})
        self.assertEqual(directory["organisations"][0]["viewerJoinRequest"]["status"], "rejected")
        reapplied = join_organisation(
            {"id": "outsider1", "role": "PUBLIC"},
            "org1",
            {"note": "I would like to apply again."},
        )
        self.assertEqual(reapplied["joinRequest"]["status"], "pending")
        self.assertNotEqual(reapplied["joinRequest"]["id"], request["id"])

    def test_admin_cannot_review_another_community_request(self):
        write_rows("community_organisations.json", [
            {"id": "org1", "name": "Org One", "status": "approved"},
            {"id": "org2", "name": "Org Two", "status": "approved"},
        ])
        write_rows("community_memberships.json", [
            {"id": "mem1", "organisationId": "org1", "userId": "admin1", "role": "ADMIN", "status": "active"},
            {"id": "mem2", "organisationId": "org2", "userId": "member1", "role": "ADMIN", "status": "active"},
        ])
        request = join_organisation({"id": "outsider1", "role": "PUBLIC"}, "org2")["joinRequest"]
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            decide_join_request({"id": "admin1", "role": "PUBLIC"}, request["id"], "approved")

    def test_admin_request_list_and_existing_user_search(self):
        join_organisation({"id": "outsider1", "role": "PUBLIC"}, "org1", {"note": "Volunteer"})
        rows = join_requests({"id": "admin1", "role": "PUBLIC"}, "org1")["joinRequests"]
        self.assertEqual(rows[0]["applicant"]["name"], "Outsider")
        candidates = member_candidates({"id": "admin1", "role": "PUBLIC"}, "org1", "out")["users"]
        self.assertEqual(candidates[0]["id"], "outsider1")

    def test_admin_can_add_existing_member_without_duplicate(self):
        first = add_member({"id": "admin1", "role": "PUBLIC"}, "org1", {"name": "Member One", "email": "m@example.test"})
        second = add_member({"id": "admin1", "role": "PUBLIC"}, "org1", {"name": "Member One", "email": "m@example.test"})
        self.assertEqual(first["member"]["id"], second["member"]["id"])
        self.assertEqual(len([row for row in members_for_org("org1") if row["userId"] == "member1"]), 1)

    def test_admin_can_create_new_member_account(self):
        result = add_member(
            {"id": "admin1", "role": "PUBLIC"},
            "org1",
            {"name": "New Member", "email": "new@example.test", "password": "secret1"},
        )
        self.assertTrue(result["createdUser"])
        self.assertEqual(result["member"]["role"], "MEMBER")

    def test_member_cannot_manage_members(self):
        with self.assertRaises(ValueError):
            add_member({"id": "member1", "role": "PUBLIC"}, "org1", {"name": "Other", "email": "o@example.test"})

    def test_admin_cannot_manage_unowned_community(self):
        write_rows("community_organisations.json", [
            {"id": "org1", "name": "Org One", "bio": "Community group", "region": "Flores", "status": "approved"},
            {"id": "org2", "name": "Org Two", "bio": "Other group", "region": "Bali", "status": "approved"},
        ])
        with self.assertRaises(ValueError):
            add_member({"id": "admin1", "role": "PUBLIC"}, "org2", {"name": "Other", "email": "o@example.test"})

    def test_super_admin_can_create_community(self):
        result = create_community({"id": "super1", "role": "ADMIN"}, {"name": "New Org", "region": "Java"})
        self.assertEqual(result["organisation"]["name"], "New Org")
        with self.assertRaises(ValueError):
            create_community({"id": "member1", "role": "PUBLIC"}, {"name": "Blocked Org"})


if __name__ == "__main__":
    unittest.main()
