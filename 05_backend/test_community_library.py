from __future__ import annotations

import unittest

from models.json_store import DATA_DIR, write_rows
from services.community_library_service import community_library, community_public_profile, member_public_contributions, member_public_profile
from services.student_work_service import public_library_projection

FILES = ["users.json", "community_organisations.json", "community_memberships.json", "community_contributions.json", "species_sightings.json", "komodo_hub.json"]


class CommunityLibraryTest(unittest.TestCase):
    def setUp(self):
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).is_file() else None for name in FILES}
        write_rows("users.json", [
            {"id": "member1", "name": "Public Member", "email": "private@example.test", "passwordHash": "secret", "role": "PUBLIC", "publicProfile": {"location": "Flores", "bio": "Reef volunteer", "interestSpecies": ["Komodo dragon"]}},
            {"id": "student1", "name": "Private Student", "email": "student@example.test", "passwordHash": "secret", "role": "STUDENT", "publicProfile": {"location": "School"}},
            {"id": "member2", "name": "Other Community", "email": "other@example.test", "role": "PUBLIC"},
        ])
        write_rows("community_organisations.json", [{"id": "org1", "name": "Org One", "bio": "One", "region": "Flores", "status": "approved"}, {"id": "org2", "name": "Org Two", "status": "approved"}])
        write_rows("community_memberships.json", [
            {"id": "m1", "organisationId": "org1", "userId": "member1", "role": "MEMBER", "status": "active"},
            {"id": "m2", "organisationId": "org1", "userId": "student1", "role": "MEMBER", "status": "active"},
            {"id": "m3", "organisationId": "org2", "userId": "member2", "role": "MEMBER", "status": "active"},
        ])
        write_rows("community_contributions.json", [
            {"id": "c1", "title": "Org one article", "body": "Published article", "type": "article", "authorId": "member1", "organisationId": "org1", "status": "published", "createdAt": "2026-10-09T10:00:00Z"},
            {"id": "c2", "title": "Other article", "body": "Other", "type": "essay", "authorId": "member2", "organisationId": "org2", "status": "published", "createdAt": "2026-10-09T09:00:00Z"},
        ])
        write_rows("species_sightings.json", [
            {"id": "s1", "speciesId": "sp1", "authorId": "member1", "organisationId": "org1", "notes": "Public sighting", "observedAt": "2026-10-08", "publicPlace": "Flores", "preciseLocation": "SECRET COORDINATES", "visibility": "public", "verificationStatus": "unverified", "createdAt": "2026-10-09T11:00:00Z"},
            {"id": "s2", "speciesId": "sp1", "authorId": "member1", "organisationId": "org1", "notes": "Private sighting", "observedAt": "2026-10-08", "publicPlace": "Flores", "preciseLocation": "SECRET", "visibility": "community", "createdAt": "2026-10-09T12:00:00Z"},
        ])
        (DATA_DIR / "komodo_hub.json").write_text('{"species":[{"id":"sp1","name":"Test Species","latin":"Species test"}]}', encoding="utf-8")

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None: path.unlink(missing_ok=True)
            else: path.write_bytes(data)

    def test_guest_library_combines_articles_and_public_sightings(self):
        result = community_library("org1")
        self.assertEqual({item["resourceType"] for item in result["items"]}, {"contribution", "sighting"})
        sighting = next(item for item in result["items"] if item["resourceType"] == "sighting")
        self.assertEqual(sighting["author"]["id"], "member1")
        self.assertNotIn("SECRET", str(result))
        self.assertNotIn("Other article", str(result))

    def test_community_profile_has_public_member_preview_only(self):
        result = community_public_profile("org1")
        self.assertEqual([member["id"] for member in result["members"]], ["member1"])
        self.assertEqual(result["librarySummary"]["total"], 2)

    def test_member_profile_and_contributions_are_public_field_mapped(self):
        result = member_public_profile("member1")
        self.assertEqual(result["member"]["location"], "Flores")
        self.assertNotIn("email", result["member"])
        self.assertNotIn("passwordHash", str(result))
        self.assertNotIn("private@example.test", str(result))
        items = member_public_contributions("member1")["items"]
        self.assertEqual({item["resourceType"] for item in items}, {"contribution", "sighting"})

    def test_student_profile_is_never_public(self):
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            member_public_profile("student1")
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            member_public_contributions("student1")

    def test_school_library_projection_remains_unchanged(self):
        row = {"id": "lib1", "publicTitle": "School work", "publicDescription": "Approved", "status": "published", "publishedAt": "now", "classId": "class1", "studentId": "student1"}
        projection = public_library_projection(row)
        self.assertEqual(projection["publicTitle"], "School work")
        self.assertNotIn("studentId", projection)


if __name__ == "__main__":
    unittest.main()
