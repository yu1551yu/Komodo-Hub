from __future__ import annotations

import unittest
from models.json_store import DATA_DIR, write_rows
from models.work_repository import list_rows
from services.account_profile_service import get_profile, patch_profile
from services.community_service import COMMENTS, POSTS, add_comment, create_student_post, list_posts, pending_for_teacher, review_post, student_posts
from services.notification_service import FILE as NOTIFICATIONS, mark_read, notifications_for
from services.learning_content_service import create_activity, set_activity_status
from services.program_service import assign_classes, create_program, set_program_status
from services.student_work_service import CONVERSATIONS, MESSAGES, conversation_messages, conversations, get_or_create_conversation, mark_read as mark_messages_read, send_message


FILES = ["users.json", "classes.json", "enrollments.json", "programs.json", "program_classes.json", "learning_activities.json", POSTS, COMMENTS, CONVERSATIONS, MESSAGES, NOTIFICATIONS]


class RepairedFlowsTest(unittest.TestCase):
    def setUp(self):
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).is_file() else None for name in FILES}
        write_rows("users.json", [{"id": "t1", "name": "Teacher A", "email": "t1@example.test", "role": "TEACHER"}, {"id": "t2", "name": "Teacher B", "email": "t2@example.test", "role": "TEACHER"}, {"id": "s1", "name": "Student A", "email": "s1@example.test", "role": "STUDENT"}])
        write_rows("classes.json", [{"id": "c1", "name": "Class A", "teacherId": "t1"}])
        write_rows("enrollments.json", [{"id": "e1", "classId": "c1", "studentId": "s1"}])
        for name in ("programs.json", "program_classes.json", "learning_activities.json", POSTS, COMMENTS, CONVERSATIONS, MESSAGES, NOTIFICATIONS): write_rows(name, [])

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None: path.unlink(missing_ok=True)
            else: path.write_bytes(data)

    def test_teacher_profile_keeps_registered_name_and_theme(self):
        status, body = patch_profile("t1", "TEACHER", {"nickname": "Guide", "profileBg": "ocean"})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["profile"]["realName"], "Teacher A")
        self.assertEqual(body["data"]["profile"]["displayName"], "Guide")
        self.assertEqual(body["data"]["profile"]["profileBg"], "ocean")
        status, invalid = patch_profile("t1", "TEACHER", {"realName": "Changed"})
        self.assertEqual(status, 400)

    def test_student_post_review_comment_and_privacy(self):
        post = create_student_post("s1", {"title": "Mangrove survey", "content": "We counted young trees."})
        self.assertEqual(list_posts(), [])
        self.assertEqual(len(pending_for_teacher("t1")), 1)
        self.assertEqual(pending_for_teacher("t2"), [])
        with self.assertRaises(ValueError): review_post("t2", post["id"], {"status": "approved"})
        review_post("t1", post["id"], {"status": "approved"})
        self.assertEqual(student_posts("s1")[0]["status"], "approved")
        self.assertEqual(notifications_for("s1")[0]["kind"], "field_note")
        public = list_posts()[0]
        self.assertIsNone(public["createdBy"])
        comment = add_comment({"id": "s1", "role": "STUDENT"}, post["id"], {"content": "Thank you"})
        self.assertEqual(comment["content"], "Thank you")
        self.assertEqual(list_posts()[0]["comments"][0]["content"], "Thank you")
        self.assertIsNone(list_posts()[0]["comments"][0]["userId"])

    def test_multiple_messages_are_appended(self):
        teacher = {"id": "t1", "role": "TEACHER"}; student = {"id": "s1", "role": "STUDENT"}
        conversation = get_or_create_conversation(teacher, "s1")
        self.assertEqual(conversation["participant"]["name"], "Student A")
        first = send_message(teacher, conversation["id"], {"content": "First"})
        second = send_message(teacher, conversation["id"], {"content": "Second"})
        rows = conversation_messages(student, conversation["id"])
        self.assertEqual([row["id"] for row in rows], [first["id"], second["id"]])
        self.assertEqual(len([row for row in notifications_for("s1") if not row["readAt"]]), 2)
        self.assertEqual(conversations(student)[0]["unreadCount"], 2)
        mark_messages_read(student, conversation["id"])
        self.assertEqual(len([row for row in notifications_for("s1") if not row["readAt"]]), 0)
        self.assertEqual(conversations(student)[0]["unreadCount"], 0)

    def test_teacher_conversations_sort_by_latest_message(self):
        users = list_rows("users.json")
        users.append({"id": "s2", "name": "Student B", "email": "s2@example.test", "role": "STUDENT"})
        write_rows("users.json", users)
        enrollments = list_rows("enrollments.json")
        enrollments.append({"id": "e2", "classId": "c1", "studentId": "s2"})
        write_rows("enrollments.json", enrollments)
        teacher = {"id": "t1", "role": "TEACHER"}
        first = get_or_create_conversation(teacher, "s1")
        second = get_or_create_conversation(teacher, "s2")
        write_rows(MESSAGES, [
            {"id": "m1", "conversationId": first["id"], "senderId": "s1", "content": "Older", "readAt": None, "createdAt": "2026-01-01T10:00:00+00:00"},
            {"id": "m2", "conversationId": second["id"], "senderId": "s2", "content": "Newest", "readAt": None, "createdAt": "2026-01-01T11:00:00+00:00"},
        ])
        rows = conversations(teacher)
        self.assertEqual(rows[0]["participant"]["name"], "Student B")
        self.assertEqual(rows[0]["unreadCount"], 1)

    def test_notification_kind_can_be_marked_read(self):
        from services.notification_service import notify
        notify("s1", "program", "New program", "Program A", "p1")
        notify("s1", "activity", "New activity", "Activity A", "a1")
        self.assertEqual(mark_read("s1", kind="program"), 1)
        rows = notifications_for("s1")
        self.assertTrue(next(row for row in rows if row["kind"] == "program")["readAt"])
        self.assertIsNone(next(row for row in rows if row["kind"] == "activity")["readAt"])

    def test_program_assignment_and_activity_publish_notify_student(self):
        program = create_program("t1", {"title": "Coastal habitats"})
        set_program_status("t1", program["id"], "published")
        assign_classes("t1", program["id"], ["c1"])
        activity = create_activity("t1", program["id"], {"title": "Survey the shore"})
        set_activity_status("t1", activity["id"], "published")
        kinds = [row["kind"] for row in notifications_for("s1")]
        self.assertCountEqual(kinds, ["program", "activity"])


if __name__ == "__main__": unittest.main()
