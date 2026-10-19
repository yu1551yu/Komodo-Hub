from __future__ import annotations

import base64
import json
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

from models.json_store import DATA_DIR

BASE = "http://127.0.0.1:5173"
FILES = ["users.json", "community_posts.json", "community_comments.json", "conversations.json", "messages.json", "notifications.json", "submissions.json"]


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
        try:
            with self.opener.open(request) as response: return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            try: return error.code, json.load(error)
            finally: error.close()


class HttpRepairedFlowsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp(prefix="komodo-http-test-"))
        cls.existed = set()
        for name in FILES:
            source = DATA_DIR / name
            if source.is_file(): shutil.copy2(source, cls.temp / name); cls.existed.add(name)

    @classmethod
    def tearDownClass(cls):
        for name in FILES:
            target = DATA_DIR / name; backup = cls.temp / name
            if name in cls.existed: shutil.copy2(backup, target)
            else: target.unlink(missing_ok=True)
        shutil.rmtree(cls.temp)

    def test_real_http_profile_publish_review_comment_and_messages(self):
        student, teacher = Client(), Client()
        self.assertEqual(student.call("POST", "/api/auth/login", {"email": "student@komodo.id", "password": "demo123"})[0], 200)
        self.assertEqual(teacher.call("POST", "/api/auth/login", {"email": "teacher@komodo.id", "password": "demo123"})[0], 200)
        self.assertEqual(teacher.call("GET", "/api/teacher/profile")[0], 200)
        status, created = student.call("POST", "/api/students/me/community-posts", {"title": "HTTP field note", "content": "Observed habitat restoration safely."})
        self.assertEqual(status, 201); post_id = created["data"]["post"]["id"]
        own_posts = student.call("GET", "/api/students/me/community-posts")[1]["data"]["posts"]
        self.assertEqual(next(row for row in own_posts if row["id"] == post_id)["status"], "pending_teacher")
        pending = teacher.call("GET", "/api/teacher/community-posts/pending")[1]
        self.assertIn(post_id, [row["id"] for row in pending["data"]["posts"]])
        self.assertEqual(teacher.call("PATCH", f"/api/teacher/community-posts/{post_id}/review", {"status": "approved"})[1]["data"]["post"]["status"], "approved")
        notices = student.call("GET", "/api/notifications")[1]["data"]["notifications"]
        notice = next(row for row in notices if row.get("resourceId") == post_id)
        self.assertIsNone(notice["readAt"])
        self.assertEqual(student.call("POST", "/api/notifications/read", {"notificationId": notice["id"]})[0], 200)
        self.assertEqual(student.call("POST", f"/api/community/posts/{post_id}/comments", {"content": "HTTP comment"})[0], 201)
        public = student.call("GET", "/api/community/posts")[1]["data"]["posts"]
        post = next(row for row in public if row["id"] == post_id)
        self.assertEqual(post["comments"][0]["content"], "HTTP comment")
        roster = teacher.call("GET", "/api/teacher/students")[1]["data"]["students"]
        self.assertTrue(roster)
        conversation = teacher.call("POST", "/api/teacher/conversations", {"participantId": roster[0]["id"]})[1]["data"]["conversation"]
        self.assertIn("participant", conversation)
        path = f"/api/teacher/conversations/{conversation['id']}/messages"
        self.assertEqual(teacher.call("POST", path, {"content": "First HTTP message"})[0], 201)
        self.assertEqual(teacher.call("POST", path, {"content": "Second HTTP message"})[0], 201)
        messages = teacher.call("GET", path)[1]["data"]["messages"]
        self.assertEqual([row["content"] for row in messages[-2:]], ["First HTTP message", "Second HTTP message"])
        self.assertEqual(student.call("GET", "/api/teacher/profile")[0], 403)
        self.assertEqual(teacher.call("POST", "/api/students/me/community-posts", {"title": "No", "content": "No"})[0], 403)
        pdf_payload = {"fileBase64": base64.b64encode(b"%PDF-1.4\nKomodo test\n").decode(), "contentType": "application/pdf", "name": "activity-guide.pdf"}
        upload_status, upload = teacher.call("POST", "/api/teacher/activity-attachments", pdf_payload)
        self.assertEqual(upload_status, 201)
        self.assertEqual(student.call("POST", "/api/teacher/activity-attachments", pdf_payload)[0], 403)
        file_id = upload["data"]["attachment"]["id"]
        for path in (DATA_DIR / "activity_attachments").glob(f"{file_id}.*"): path.unlink(missing_ok=True)
        image_payload = {"fileBase64": base64.b64encode(b"test-image-bytes").decode(), "contentType": "image/png", "name": "habitat.png"}
        image_status, image_upload = teacher.call("POST", "/api/teacher/activity-attachments", image_payload)
        self.assertEqual(image_status, 201)
        self.assertEqual(image_upload["data"]["attachment"]["contentType"], "image/png")
        image_id = image_upload["data"]["attachment"]["id"]
        for path in (DATA_DIR / "activity_attachments").glob(f"{image_id}.*"): path.unlink(missing_ok=True)
        upload_status, upload = student.call("POST", "/api/students/me/attachments", pdf_payload)
        self.assertEqual(upload_status, 201)
        student_file_id = upload["data"]["attachment"]["id"]
        for path in (DATA_DIR / "submission_uploads").rglob(f"{student_file_id}.*"): path.unlink(missing_ok=True)


if __name__ == "__main__": unittest.main()
