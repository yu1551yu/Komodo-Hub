from __future__ import annotations

import unittest

from models.json_store import DATA_DIR, write_rows
from services.conservation_program_service import (
    assign_member,
    assign_members,
    enroll_self,
    apply_to_program,
    organisation_program_applications,
    review_program_application,
    program_detail,
    public_programs,
)
from models.conservation_program_repository import list_enrollments

FILES = [
    "users.json",
    "community_organisations.json",
    "community_memberships.json",
    "conservation_programs.json",
    "program_enrollments.json",
    "program_join_requests.json",
]


class ConservationProgramsTest(unittest.TestCase):
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
                {"id": "other1", "name": "Other One", "email": "o@example.test", "role": "PUBLIC"},
            ],
        )
        write_rows(
            "community_organisations.json",
            [
                {"id": "org1", "name": "Org One", "status": "approved"},
                {"id": "org2", "name": "Org Two", "status": "approved"},
            ],
        )
        write_rows(
            "community_memberships.json",
            [
                {"id": "mem1", "organisationId": "org1", "userId": "admin1", "role": "ADMIN", "status": "active"},
                {"id": "mem2", "organisationId": "org1", "userId": "member1", "role": "MEMBER", "status": "active"},
                {"id": "mem3", "organisationId": "org2", "userId": "other1", "role": "MEMBER", "status": "active"},
            ],
        )
        write_rows(
            "conservation_programs.json",
            [
                {
                    "id": "cp1",
                    "title": "Community Reef Watch",
                    "summary": "Watch reefs",
                    "description": "Community survey",
                    "participationInfo": "Open",
                    "status": "published",
                    "allowedParticipantTypes": ["individual", "community"],
                },
                {
                    "id": "cp2",
                    "title": "Individual Only",
                    "summary": "Solo",
                    "description": "Individual program",
                    "participationInfo": "Open",
                    "status": "published",
                    "allowedParticipantTypes": ["individual"],
                },
            ],
        )
        write_rows("program_enrollments.json", [])
        write_rows("program_join_requests.json", [])

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)

    def test_guest_can_browse_and_open_program(self):
        self.assertEqual(public_programs()["programs"][0]["id"], "cp1")
        self.assertEqual(program_detail("cp1")["program"]["title"], "Community Reef Watch")

    def test_signed_in_user_can_enroll_self(self):
        result = enroll_self({"id": "member1", "role": "PUBLIC"}, "cp1")
        self.assertTrue(result["created"])
        mine = program_detail("cp1", {"id": "member1", "role": "PUBLIC"})
        self.assertEqual(mine["program"]["viewerEnrollment"]["userId"], "member1")

    def test_admin_can_assign_member_without_duplicates(self):
        actor = {"id": "admin1", "role": "PUBLIC"}
        first = assign_member(actor, "org1", {"userId": "member1", "programId": "cp1"})
        second = assign_member(actor, "org1", {"userId": "member1", "programId": "cp1"})
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(len(list_enrollments()), 1)

    def test_admin_can_batch_assign_members_and_refresh_participants(self):
        result = assign_members({"id": "admin1", "role": "PUBLIC"}, "org1", {"programId": "cp1", "userIds": ["admin1", "member1", "member1"]})
        self.assertEqual(result["createdCount"], 2)
        detail = program_detail("cp1")
        self.assertEqual(detail["program"]["participantCount"], 2)
        self.assertEqual({row["name"] for row in detail["program"]["participants"]}, {"Admin One", "Member One"})
        repeated = assign_members({"id": "admin1", "role": "PUBLIC"}, "org1", {"programId": "cp1", "userIds": ["member1"]})
        self.assertEqual(repeated["createdCount"], 0)

    def test_member_cannot_assign_programs(self):
        with self.assertRaises(ValueError):
            assign_member({"id": "member1", "role": "PUBLIC"}, "org1", {"userId": "member1", "programId": "cp1"})

    def test_admin_cannot_assign_cross_community_member(self):
        with self.assertRaises(ValueError):
            assign_member({"id": "admin1", "role": "PUBLIC"}, "org1", {"userId": "other1", "programId": "cp1"})

    def test_community_assignment_respects_program_rules(self):
        with self.assertRaises(ValueError):
            assign_member({"id": "admin1", "role": "PUBLIC"}, "org1", {"userId": "member1", "programId": "cp2"})

    def test_member_applies_and_admin_approval_creates_enrollment(self):
        submitted = apply_to_program({"id": "member1", "role": "PUBLIC"}, "cp1", {"organisationId": "org1", "note": "I can help with surveys."})
        self.assertEqual(submitted["application"]["status"], "pending")
        self.assertEqual(list_enrollments(), [])
        queue = organisation_program_applications({"id": "admin1", "role": "PUBLIC"}, "org1")
        self.assertEqual(queue["applications"][0]["applicant"]["name"], "Member One")
        reviewed = review_program_application({"id": "admin1", "role": "PUBLIC"}, "org1", submitted["application"]["id"], {"status": "approved"})
        self.assertEqual(reviewed["application"]["status"], "approved")
        self.assertEqual(len(list_enrollments()), 1)

    def test_duplicate_pending_application_is_not_created(self):
        actor = {"id": "member1", "role": "PUBLIC"}
        first = apply_to_program(actor, "cp1", {"organisationId": "org1"})
        second = apply_to_program(actor, "cp1", {"organisationId": "org1"})
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])

    def test_member_and_cross_organisation_admin_cannot_review(self):
        request = apply_to_program({"id": "member1", "role": "PUBLIC"}, "cp1", {"organisationId": "org1"})["application"]
        with self.assertRaises(ValueError):
            organisation_program_applications({"id": "member1", "role": "PUBLIC"}, "org1")
        with self.assertRaises(ValueError):
            review_program_application({"id": "other1", "role": "PUBLIC"}, "org2", request["id"], {"status": "approved"})

    def test_rejection_does_not_create_enrollment_and_allows_reapply(self):
        actor = {"id": "member1", "role": "PUBLIC"}
        request = apply_to_program(actor, "cp1", {"organisationId": "org1"})["application"]
        review_program_application({"id": "admin1", "role": "PUBLIC"}, "org1", request["id"], {"status": "rejected"})
        self.assertEqual(list_enrollments(), [])
        self.assertTrue(apply_to_program(actor, "cp1", {"organisationId": "org1"})["created"])


if __name__ == "__main__":
    unittest.main()
