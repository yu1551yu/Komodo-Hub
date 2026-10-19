from __future__ import annotations

import unittest

from models.json_store import DATA_DIR, write_rows
from models.work_repository import list_rows
from services.contribution_service import add_comment, contribution_comments, contribution_detail, create, my_contributions, public_contributions, read_comment, received_comments

FILES = ["users.json", "community_organisations.json", "community_memberships.json", "community_contributions.json", "contribution_comments.json"]


class ContributionsTest(unittest.TestCase):
    def setUp(self):
        self.backup = {
            name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).is_file() else None
            for name in FILES
        }
        write_rows(
            "users.json",
            [
                {"id": "member1", "name": "Member One", "email": "m@example.test", "role": "PUBLIC"},
                {"id": "other1", "name": "Other One", "email": "o@example.test", "role": "PUBLIC"},
                {"id": "student1", "name": "Private Student", "email": "s@example.test", "role": "STUDENT"},
            ],
        )
        write_rows("community_organisations.json", [{"id": "org1", "name": "Org One", "status": "approved"}])
        write_rows("community_memberships.json", [{"id": "mem1", "organisationId": "org1", "userId": "member1", "role": "MEMBER", "status": "active"}])
        write_rows("community_contributions.json", [])
        write_rows("contribution_comments.json", [])

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)

    def test_member_can_create_and_guest_can_read(self):
        result = create({"id": "member1", "role": "PUBLIC"}, {"organisationId": "org1", "type": "article", "title": "Reef notes", "body": "Useful reef protection notes."})
        saved = list_rows("community_contributions.json")[0]
        self.assertEqual(saved["authorId"], "member1")
        self.assertEqual(saved["organisationId"], "org1")
        public = public_contributions()["contributions"][0]
        self.assertEqual(public["title"], "Reef notes")
        self.assertEqual(public["author"]["name"], "Member One")
        self.assertNotIn("email", public["author"])
        detail = contribution_detail(result["contribution"]["id"])["contribution"]
        self.assertEqual(detail["community"]["name"], "Org One")

    def test_author_identity_comes_from_session_actor(self):
        result = create(
            {"id": "member1", "role": "PUBLIC"},
            {"organisationId": "org1", "authorId": "other1", "type": "essay", "title": "My essay", "body": "Body"},
        )
        self.assertEqual(result["contribution"]["author"]["id"], "member1")
        self.assertEqual(my_contributions({"id": "member1"})["contributions"][0]["id"], result["contribution"]["id"])

    def test_non_member_cannot_publish_for_community(self):
        with self.assertRaises(ValueError):
            create({"id": "other1", "role": "PUBLIC"}, {"organisationId": "org1", "type": "article", "title": "No", "body": "No"})

    def test_registered_public_user_can_publish_personally_without_membership(self):
        result = create({"id": "other1", "role": "PUBLIC"}, {"organisationId": "", "type": "article", "title": "Personal field note", "body": "A personal conservation reflection."})
        saved = list_rows("community_contributions.json")[0]
        self.assertIsNone(saved["organisationId"])
        self.assertIsNone(saved["libraryStatus"])
        self.assertIsNone(result["contribution"]["community"])
        self.assertEqual(public_contributions()["contributions"][0]["title"], "Personal field note")

    def test_missing_contribution_and_xss_escape(self):
        with self.assertRaises(ValueError):
            contribution_detail("missing")
        result = create(
            {"id": "member1", "role": "PUBLIC"},
            {"organisationId": "org1", "type": "column", "title": "<b>Title</b>", "body": "<script>alert(1)</script>"},
        )
        self.assertEqual(result["contribution"]["title"], "&lt;b&gt;Title&lt;/b&gt;")
        self.assertIn("&lt;script&gt;", result["contribution"]["body"])

    def test_comments_are_persisted_unread_and_marked_read_by_owner(self):
        contribution = create({"id": "member1", "role": "PUBLIC"}, {"organisationId": "org1", "type": "article", "title": "Reef notes", "body": "Body"})["contribution"]
        comment = add_comment({"id": "other1", "role": "PUBLIC"}, contribution["id"], {"content": "Useful article"})["comment"]
        self.assertEqual(contribution_comments(contribution["id"])["comments"][0]["content"], "Useful article")
        received = received_comments({"id": "member1", "role": "PUBLIC"})
        self.assertEqual(received["unreadCount"], 1)
        self.assertEqual(received["comments"][0]["contribution"]["title"], "Reef notes")
        read_comment({"id": "member1", "role": "PUBLIC"}, comment["id"])
        self.assertEqual(received_comments({"id": "member1", "role": "PUBLIC"})["unreadCount"], 0)
        with self.assertRaises(ValueError):
            read_comment({"id": "other1", "role": "PUBLIC"}, comment["id"])

    def test_student_commenter_is_anonymous(self):
        contribution = create({"id": "member1", "role": "PUBLIC"}, {"organisationId": "org1", "type": "article", "title": "Forest notes", "body": "Body"})["contribution"]
        comment = add_comment({"id": "student1", "role": "STUDENT"}, contribution["id"], {"content": "Student response"})["comment"]
        self.assertEqual(comment["author"]["name"], "Student naturalist")
        self.assertNotIn("id", comment["author"])


if __name__ == "__main__":
    unittest.main()
