from __future__ import annotations

import unittest
from pathlib import Path

from models.json_store import DATA_DIR, read_rows, write_rows
from services.learning_access_service import AccessError
from services.progress_service import student_program_progress
from services.student_work_service import (
    FEEDBACK, LIBRARY, MESSAGES, PORTFOLIO, SUBMISSIONS,
    add_feedback, add_portfolio_item, get_or_create_conversation,
    public_library_projection, save_submission, student_material,
    return_submission, teacher_submission, teacher_submissions, upsert_library_item,
)


FILES = ["users.json", "classes.json", "enrollments.json", "programs.json", "program_classes.json", "materials.json", "learning_activities.json", SUBMISSIONS, FEEDBACK, MESSAGES, "conversations.json", PORTFOLIO, LIBRARY, "notifications.json"]


class WorkflowPermissionsTest(unittest.TestCase):
    def setUp(self):
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).is_file() else None for name in FILES}
        write_rows("users.json", [{"id": "t1", "name": "Teacher A", "role": "TEACHER"}, {"id": "t2", "name": "Teacher B", "role": "TEACHER"}, {"id": "s1", "name": "Student A", "role": "STUDENT"}, {"id": "s2", "name": "Student B", "role": "STUDENT"}])
        write_rows("classes.json", [{"id": "c1", "name": "A", "teacherId": "t1"}, {"id": "c2", "name": "B", "teacherId": "t2"}])
        write_rows("enrollments.json", [{"id": "e1", "classId": "c1", "studentId": "s1"}, {"id": "e2", "classId": "c2", "studentId": "s2"}])
        write_rows("programs.json", [{"id": "p1", "title": "Program A", "teacherId": "t1", "status": "published"}, {"id": "p2", "title": "Program B", "teacherId": "t2", "status": "published"}])
        write_rows("program_classes.json", [{"id": "pc1", "programId": "p1", "classId": "c1"}, {"id": "pc2", "programId": "p2", "classId": "c2"}])
        write_rows("materials.json", [{"id": "m1", "programId": "p1", "title": "Published", "status": "published", "resourceRef": "https://example.org"}, {"id": "m2", "programId": "p1", "title": "Draft", "status": "draft"}])
        write_rows("learning_activities.json", [{"id": "a1", "programId": "p1", "title": "One", "status": "published"}, {"id": "a2", "programId": "p1", "title": "Two", "status": "published"}, {"id": "a3", "programId": "p1", "title": "Draft", "status": "draft"}, {"id": "a4", "programId": "p1", "title": "Closed", "status": "closed"}])
        for name in (SUBMISSIONS, FEEDBACK, MESSAGES, "conversations.json", PORTFOLIO, LIBRARY, "notifications.json"): write_rows(name, [])

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)

    def test_material_and_activity_access(self):
        self.assertEqual(student_material("s1", "m1")["title"], "Published")
        with self.assertRaises(AccessError): student_material("s1", "m2")
        with self.assertRaises(AccessError): student_material("s2", "m1")
        with self.assertRaises(ValueError): save_submission("s1", "a4", {"content": "late"})

    def test_submission_feedback_portfolio_and_teacher_ownership(self):
        submission = save_submission("s1", "a1", {"content": "field work", "action": "save"})
        updated = save_submission("s1", "a1", {"content": "updated", "action": "submit"})
        self.assertEqual(submission["id"], updated["id"])
        self.assertEqual(updated["status"], "submitted")
        with self.assertRaises(ValueError):
            save_submission("s1", "a1", {"content": "locked", "action": "save"})
        self.assertEqual(teacher_submission("t1", submission["id"])["student"]["name"], "Student A")
        with self.assertRaises(AccessError): teacher_submission("t2", submission["id"])
        feedback = add_feedback({"id": "t1", "role": "TEACHER"}, submission["id"], {"content": "Good evidence"})
        add_feedback({"id": "s1", "role": "STUDENT"}, submission["id"], {"content": "Thank you", "parentFeedbackId": feedback["id"]})
        with self.assertRaises(AccessError): add_feedback({"id": "s2", "role": "STUDENT"}, submission["id"], {"content": "bad", "parentFeedbackId": feedback["id"]})
        self.assertEqual(add_portfolio_item("s1", {"submissionId": submission["id"]})["studentId"], "s1")
        with self.assertRaises(AccessError): add_portfolio_item("s2", {"submissionId": submission["id"]})

    def test_submission_draft_submit_return_and_resubmit(self):
        draft = save_submission("s1", "a1", {"content": "first draft", "action": "save"})
        self.assertEqual(draft["status"], "draft")
        with self.assertRaises(ValueError):
            add_portfolio_item("s1", {"submissionId": draft["id"]})
        self.assertEqual(teacher_submissions("t1", "a1"), [])
        with self.assertRaises(AccessError):
            teacher_submission("t1", draft["id"])
        submitted = save_submission("s1", "a1", {"content": "ready", "action": "submit"})
        self.assertEqual(submitted["status"], "submitted")
        returned = return_submission("t1", submitted["id"], {"note": "Add one more observation"})
        self.assertEqual(returned["status"], "returned")
        revised = save_submission("s1", "a1", {"content": "revised observation", "action": "save"})
        self.assertEqual(revised["status"], "draft")
        final = save_submission("s1", "a1", {"content": "final observation", "action": "submit"})
        self.assertEqual(final["status"], "submitted")

    def test_progress_zero_partial_complete(self):
        self.assertEqual(student_program_progress("s1", "p1")["percentage"], 0)
        save_submission("s1", "a1", {"content": "one"})
        self.assertEqual(student_program_progress("s1", "p1")["percentage"], 33)
        save_submission("s1", "a2", {"content": "two"})
        with self.assertRaises(ValueError): save_submission("s1", "a4", {"content": "closed"})
        write_rows("learning_activities.json", [row for row in read_rows("learning_activities.json") if row["id"] != "a4"])
        self.assertEqual(student_program_progress("s1", "p1")["percentage"], 100)

    def test_messaging_and_library_privacy(self):
        self.assertEqual(get_or_create_conversation({"id": "t1", "role": "TEACHER"}, "s1")["studentId"], "s1")
        with self.assertRaises(AccessError): get_or_create_conversation({"id": "t1", "role": "TEACHER"}, "s2")
        with self.assertRaises(AccessError): get_or_create_conversation({"id": "s1", "role": "STUDENT"}, "s2")
        submission = save_submission("s1", "a1", {"content": "library work"})
        item = upsert_library_item("t1", submission["id"], {"publicTitle": "Habitat notes", "publicDescription": "Safe summary", "status": "published"})
        projection = public_library_projection(item)
        self.assertNotIn("studentId", projection)
        self.assertNotIn("submissionId", projection)
        self.assertNotIn("email", projection)
        with self.assertRaises(AccessError): upsert_library_item("t2", submission["id"], {"publicTitle": "No", "status": "published"})


if __name__ == "__main__":
    unittest.main()
