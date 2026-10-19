"""Isolated tests: actual repositories/HTTP routes, in-memory database adapter.

No connection to the configured MySQL database and no production data writes.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import json
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from services.review_reminder_service import review_state, teacher_review_summary
from services.student_work_service import add_feedback, return_submission, save_submission

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


class ReviewReminderTest(unittest.TestCase):
    def setUp(self):
        self.rows = {
            "users.json": [{"id": uid, "name": name, "role": role, "email": f"{uid}@example.test"} for uid, name, role in [
                ("t1", "Teacher One", "TEACHER"), ("t2", "Teacher Two", "TEACHER"),
                ("s1", "Student One", "STUDENT"), ("s2", "Student Two", "STUDENT"),
                ("admin", "Admin", "ADMIN"), ("public", "Public", "PUBLIC")]],
            "classes.json": [{"id": "c1", "teacherId": "t1", "name": "Class One"}, {"id": "c2", "teacherId": "t2", "name": "Class Two"}],
            "enrollments.json": [{"id": "e1", "classId": "c1", "studentId": "s1"}, {"id": "e2", "classId": "c2", "studentId": "s2"}],
            "programs.json": [{"id": "p1", "teacherId": "t1", "title": "Program One", "status": "published"}, {"id": "p2", "teacherId": "t2", "title": "Program Two", "status": "published"}],
            "program_classes.json": [{"id": "pc1", "programId": "p1", "classId": "c1"}, {"id": "pc2", "programId": "p2", "classId": "c2"}],
            "learning_activities.json": [{"id": "a1", "programId": "p1", "title": "Habitat journal", "status": "published"}, {"id": "a2", "programId": "p2", "title": "Other teacher activity", "status": "published"}],
            "submissions.json": [self.submission("old", 25), self.submission("new", 1), self.submission("oldest", 30), self.submission("other", 40, studentId="s2", activityId="a2")],
        }
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("database.store.read_rows", side_effect=lambda name: deepcopy(self.rows.get(name, []))))
        self.stack.enter_context(patch("database.store.write_rows", side_effect=lambda name, rows: self.rows.__setitem__(name, deepcopy(rows))))
        self.stack.enter_context(patch("database.connection.connection", side_effect=AssertionError("Tests must not connect to MySQL")))
        self.stack.enter_context(patch("services.review_reminder_service.utc_now", return_value=NOW))
        self.stack.enter_context(patch("routes.teacher_work.utc_now", return_value=NOW))
        self.stack.enter_context(patch("auth.middleware.get_user_id_for_token", side_effect=lambda token: token if token in {"t1", "t2", "s1", "s2", "admin", "public"} else None))

    @staticmethod
    def submission(record_id, hours, **extra):
        return {"id": record_id, "studentId": "s1", "activityId": "a1", "status": "submitted",
                "content": "Habitat observations", "attachments": [], "submittedAt": (NOW - timedelta(hours=hours)).isoformat(), **extra}

    def test_threshold_boundary_and_timezone(self):
        for age, overdue in [(23, False), (24, False), (25, True)]:
            with self.subTest(age=age):
                self.assertEqual(review_state(self.submission("x", age), NOW)["overdue"], overdue)
        exact = self.submission("x", 24)
        self.assertTrue(review_state(exact, NOW + timedelta(seconds=1))["overdue"])
        same_in_china = (NOW - timedelta(hours=25)).astimezone(timezone(timedelta(hours=8))).isoformat()
        self.assertTrue(review_state({**exact, "submittedAt": same_in_china}, NOW)["overdue"])

    def test_only_submitted_work_is_pending(self):
        for status in ["draft", "reviewed", "returned"]:
            with self.subTest(status=status):
                state = review_state(self.submission("x", 30, status=status), NOW)
                self.assertFalse(state["pending"])
                self.assertFalse(state["overdue"])

    def test_bad_or_missing_timestamps_do_not_crash_or_use_creation_time(self):
        for stamp in [None, "", "invalid", "2026-10-16T10:00:00", 123, "9999-12-31T23:00:00+00:00"]:
            with self.subTest(stamp=stamp):
                result = review_state(self.submission("x", 30, submittedAt=stamp, createdAt="2020-01-01T00:00:00+00:00"), NOW)
                self.assertTrue(result["pending"])
                self.assertFalse(result["overdue"])
                self.assertFalse(result["timingAvailable"])

    def test_future_submission_is_not_overdue(self):
        state = review_state(self.submission("x", -1), NOW)
        self.assertEqual(state["waitingSeconds"], 0)
        self.assertFalse(state["overdue"])

    def test_summary_counts_order_and_teacher_scope(self):
        original = deepcopy(self.rows)
        summary = teacher_review_summary("t1", NOW)
        self.assertEqual((summary["pendingCount"], summary["overdueCount"]), (3, 2))
        self.assertEqual([item["id"] for item in summary["items"]], ["oldest", "old", "new"])
        self.assertEqual([item["id"] for item in teacher_review_summary("t2", NOW)["items"]], ["other"])
        self.assertEqual(self.rows, original)

    def test_old_teacher_loses_reminders_after_student_moves(self):
        self.rows["enrollments.json"][0]["classId"] = "c2"
        self.assertEqual(teacher_review_summary("t1", NOW)["pendingCount"], 0)
        # New class membership alone must not bypass existing program ownership.
        self.assertEqual([item["id"] for item in teacher_review_summary("t2", NOW)["items"]], ["other"])

    def test_feedback_removes_reminder_using_existing_review_flow(self):
        add_feedback({"id": "t1", "role": "TEACHER"}, "old", {"content": "Reviewed habitat evidence"})
        summary = teacher_review_summary("t1", NOW)
        self.assertEqual((summary["pendingCount"], summary["overdueCount"]), (2, 1))
        self.assertNotIn("old", [item["id"] for item in summary["items"]])

    def test_return_and_resubmit_restart_review_clock(self):
        self.rows["submissions.json"] = [self.submission("old", 25)]
        return_submission("t1", "old", {"note": "Please add evidence"})
        self.assertEqual(teacher_review_summary("t1", NOW)["pendingCount"], 0)
        with patch("models.json_store.now_iso", return_value=NOW.isoformat()):
            saved = save_submission("s1", "a1", {"content": "Additional evidence", "action": "submit"})
        self.assertEqual(saved["submittedAt"], NOW.isoformat())
        self.assertEqual(teacher_review_summary("t1", NOW)["overdueCount"], 0)
        self.assertEqual(teacher_review_summary("t1", NOW)["pendingCount"], 1)

    def start_http(self):
        from server import KomodoHandler

        class QuietHandler(KomodoHandler):
            def log_message(self, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        def stop():
            httpd.shutdown()
            httpd.server_close()
            thread.join()

        self.addCleanup(stop)
        return f"http://127.0.0.1:{httpd.server_port}"

    @staticmethod
    def call(base, path, actor=None, body=None):
        headers = {"Cookie": f"komodo_session={actor}"} if actor else {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(base + path, headers=headers, data=json.dumps(body).encode() if body is not None else None)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_http_authentication_and_roles(self):
        base = self.start_http()
        for actor, expected in [(None, 401), ("s1", 403), ("public", 403), ("admin", 403), ("t1", 200)]:
            with self.subTest(actor=actor):
                self.assertEqual(self.call(base, "/api/teacher/review-reminders", actor)[0], expected)

    def test_http_summary_and_existing_list_detail_are_connected(self):
        base = self.start_http()
        status, body = self.call(base, "/api/teacher/review-reminders", "t1")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["reviewSummary"]["overdueCount"], 2)
        status, body = self.call(base, "/api/teacher/activities/a1/submissions", "t1")
        self.assertEqual(status, 200)
        self.assertTrue(next(item for item in body["data"]["submissions"] if item["id"] == "old")["review"]["overdue"])
        status, body = self.call(base, "/api/teacher/submissions/old", "t1")
        self.assertEqual(status, 200)
        self.assertTrue(body["data"]["submission"]["review"]["overdue"])
        self.assertEqual(self.call(base, "/api/teacher/submissions/old", "t2")[0], 403)

    def test_http_review_updates_summary_immediately(self):
        base = self.start_http()
        self.assertEqual(self.call(base, "/api/teacher/submissions/old/feedback", "t1", {"content": "Good evidence"})[0], 201)
        summary = self.call(base, "/api/teacher/review-reminders", "t1")[1]["data"]["reviewSummary"]
        self.assertEqual(summary["overdueCount"], 1)
        self.assertEqual(summary["pendingCount"], 2)

    def test_summary_failure_does_not_show_false_zero(self):
        from routes.review_reminders import summary
        with patch("routes.review_reminders.require_role", return_value=({"id": "t1"}, None)), patch("routes.review_reminders.teacher_review_summary", side_effect=RuntimeError("storage offline")):
            status, body = summary(object())
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "REVIEW_REMINDERS_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
