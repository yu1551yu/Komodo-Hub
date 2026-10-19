from __future__ import annotations

import unittest
from models.json_store import DATA_DIR, write_rows
from services.community_library_service import community_library
from services.contribution_review_service import review, review_queue
from services.contribution_service import create, public_contributions


class ContributionReviewTest(unittest.TestCase):
    def setUp(self):
        self.files = ["users.json", "community_organisations.json", "community_memberships.json", "community_contributions.json", "species_sightings.json", "program_enrollments.json"]
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).exists() else None for name in self.files}
        write_rows("users.json", [{"id": "admin1", "name": "Org Admin", "role": "PUBLIC"}, {"id": "member1", "name": "Member", "role": "PUBLIC"}, {"id": "other1", "name": "Other", "role": "PUBLIC"}])
        write_rows("community_organisations.json", [{"id": "org1", "name": "Org", "status": "approved"}])
        write_rows("community_memberships.json", [{"id": "a", "organisationId": "org1", "userId": "admin1", "role": "ADMIN", "status": "active"}, {"id": "m", "organisationId": "org1", "userId": "member1", "role": "MEMBER", "status": "active"}])
        write_rows("community_contributions.json", [])
        write_rows("species_sightings.json", [])
        write_rows("program_enrollments.json", [])

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None: path.unlink(missing_ok=True)
            else: path.write_bytes(data)

    def test_contribution_is_in_community_before_library_approval(self):
        item = create({"id": "member1"}, {"organisationId": "org1", "type": "article", "title": "Forest", "body": "Field evidence"})["contribution"]
        self.assertEqual(item["libraryStatus"], "pending")
        self.assertEqual(len(public_contributions()["contributions"]), 1)
        self.assertEqual(community_library("org1")["items"], [])
        self.assertEqual(review_queue({"id": "admin1"}, "org1")["items"][0]["id"], item["id"])
        review({"id": "admin1"}, "org1", "contribution", item["id"], "approved")
        self.assertEqual(community_library("org1")["items"][0]["id"], item["id"])

    def test_only_org_admin_can_review_and_rejection_requires_reason(self):
        item = create({"id": "member1"}, {"organisationId": "org1", "type": "essay", "title": "Coast", "body": "Notes"})["contribution"]
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            review({"id": "member1"}, "org1", "contribution", item["id"], "approved")
        with self.assertRaisesRegex(ValueError, "REASON_REQUIRED"):
            review({"id": "admin1"}, "org1", "contribution", item["id"], "rejected")
        review({"id": "admin1"}, "org1", "contribution", item["id"], "rejected", "Needs clearer evidence")
        self.assertEqual(community_library("org1")["items"], [])


if __name__ == "__main__":
    unittest.main()
