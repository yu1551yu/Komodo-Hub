#!/usr/bin/env python3
"""
Komodo Hub - static UI + MySQL persistence and role-based APIs.

Run from repo root:
  python 05_backend/server.py
"""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.handlers import handle_change_password, handle_login, handle_logout, handle_me, handle_register
from auth.sessions import COOKIE_NAME
from models.user_repository import seed_admin_user_if_missing, seed_public_users_if_missing, seed_users_if_empty
from models.class_repository import seed_classes_if_empty
from models.enrollment_repository import seed_enrollments_if_empty
from routes.classes import handle_join_class
from routes.student import (
    handle_dashboard as student_dashboard,
    handle_get_avatar,
    handle_my_classes,
    handle_my_profile,
    handle_patch_my_profile,
    handle_upload_avatar,
)
from routes.student_learning import get_dashboard as student_learning_dashboard, get_my_program, list_my_programs
from routes.teacher import (
    handle_create_class,
    handle_get_student,
    handle_list_classes,
    handle_list_students,
    handle_regenerate_access_code,
    handle_get_class,
    handle_patch_class,
    handle_class_students,
    handle_remove_student,
)
from routes.teacher_learning import (
    activity_status, get_program, list_programs, material_status, patch_activity,
    patch_material, patch_program, post_activity, post_material, post_program,
    program_classes, program_status, upload_activity_attachment,
)
from routes import student_work, teacher_work, admin_organisations
from routes import review_reminders
from routes import community, community_library, community_portal, conservation_programs, contribution_reviews, contributions, creative_canvas, notifications, organisation_admin_invitations, public_profile, sightings, species, teacher_profile
from routes.learning_files import activity_file
from routes.submission_files import submission_file
from database.connection import connection, initialize_database
from database.schema import create_schema
from database.store import read_document, replace_species, write_document

DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "komodo_hub.json"
REACT_DIST = ROOT.parent / "komodo-hub-react" / "dist"
# Preserve the existing interface even when a React build is present.
STATIC_DIR = ROOT.parent / "04_web_prototype"
HOST = os.environ.get("KOMODO_HOST", "127.0.0.1")
PORT = int(os.environ.get("KOMODO_PORT", "5173"))


class KomodoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _read_body_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, status: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_bytes(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-store")
        self.end_headers()
        self.wfile.write(body)

    def _api_json(self, status: int, obj: dict, set_cookie: str | None = None, clear_cookie: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{COOKIE_NAME}={set_cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age={14 * 24 * 3600}",
            )
        if clear_cookie:
            self.send_header(
                "Set-Cookie",
                f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
            )
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _dispatch_api(self, method: str, path: str, query: str = "") -> bool:
        def json_body():
            try:
                return self._read_body_json() or {}, None
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None, {"ok": False, "error": {"code": "INVALID_JSON", "message": "Invalid JSON."}}

        def reply(result):
            status, payload = result
            self._api_json(status, payload)
            return True

        parts = [unquote(part) for part in path.strip("/").split("/")]

        if path == "/api/teacher/review-reminders" and method == "GET":
            return reply(review_reminders.summary(self))

        if path == "/api/admin/organizations":
            params = parse_qs(query)
            if method == "GET": return reply(admin_organisations.index(self, (params.get("q") or [""])[0], (params.get("status") or [""])[0]))
            if method == "POST":
                body, err = json_body(); return reply((400, err) if err else admin_organisations.create(self, body))
        if path == "/api/admin/organizations/stats" and method == "GET": return reply(admin_organisations.statistics(self))
        if path == "/api/admin/users/search" and method == "GET":
            params = parse_qs(query); return reply(admin_organisations.users(self, (params.get("q") or [""])[0]))
        if path == "/api/organization-admin/invitations" and method == "GET": return reply(organisation_admin_invitations.index(self))
        if len(parts) == 5 and parts[:3] == ["api", "organization-admin", "invitations"] and parts[4] == "decision" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else organisation_admin_invitations.decision(self, parts[3], body))
        if len(parts) == 4 and parts[:3] == ["api", "admin", "organizations"]:
            if method == "GET": return reply(admin_organisations.detail(self, parts[3]))
            if method == "PATCH":
                body, err = json_body(); return reply((400, err) if err else admin_organisations.update(self, parts[3], body))
        if len(parts) == 5 and parts[:3] == ["api", "admin", "organizations"]:
            if parts[4] == "status" and method == "PATCH":
                body, err = json_body(); return reply((400, err) if err else admin_organisations.status(self, parts[3], body))
            if parts[4] == "administrator" and method == "PUT":
                body, err = json_body(); return reply((400, err) if err else admin_organisations.administrator(self, parts[3], body))

        if path == "/api/species" and method == "GET":
            params = parse_qs(query)
            return reply(species.index((params.get("q") or [""])[0]))
        if len(parts) == 3 and parts[:2] == ["api", "species"] and method == "GET":
            return reply(species.detail(parts[2]))
        if path == "/api/sightings" and method == "GET":
            return reply(sightings.index())
        if path == "/api/sightings" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else sightings.post(self, body))
        if path == "/api/me/sightings" and method == "GET":
            return reply(sightings.mine(self))
        if len(parts) == 3 and parts[:2] == ["api", "sightings"] and method == "GET":
            return reply(sightings.detail(parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "sightings" and method == "GET":
            return reply(sightings.community(self, parts[2]))
        if path == "/api/programs" and method == "GET":
            return reply(conservation_programs.index(self))
        if path == "/api/contributions" and method == "GET":
            params = parse_qs(query)
            return reply(contributions.index({"organisationId": (params.get("organisationId") or [""])[0] or None}))
        if path == "/api/contributions" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else contributions.post(self, body))
        if path == "/api/me/contributions" and method == "GET":
            return reply(contributions.mine(self))
        if path == "/api/me/contribution-comments" and method == "GET":
            return reply(contributions.received(self))
        if len(parts) == 4 and parts[:2] == ["api", "contributions"] and parts[3] == "comments":
            if method == "GET": return reply(contributions.comments(parts[2]))
            if method == "POST":
                body, err = json_body(); return reply((400, err) if err else contributions.comment(self, parts[2], body))
        if len(parts) == 4 and parts[:2] == ["api", "contribution-comments"] and parts[3] == "read" and method == "PATCH":
            return reply(contributions.read(self, parts[2]))
        if len(parts) == 3 and parts[:2] == ["api", "contributions"] and method == "GET":
            return reply(contributions.detail(parts[2]))
        if path == "/api/me/program-enrollments" and method == "GET":
            return reply(conservation_programs.me(self))
        if len(parts) == 3 and parts[:2] == ["api", "programs"] and method == "GET":
            return reply(conservation_programs.detail(self, parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "programs"] and parts[3] == "enroll" and method == "POST":
            return reply(conservation_programs.self_enroll(self, parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "programs"] and parts[3] == "applications" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else conservation_programs.apply(self, parts[2], body))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "program-enrollments" and method == "GET":
            return reply(conservation_programs.community_context(self, parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "program-enrollments" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else conservation_programs.community_assign(self, parts[2], body))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "programs" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else conservation_programs.community_program_save(self, parts[2], body))
        if len(parts) == 5 and parts[:2] == ["api", "communities"] and parts[3] == "programs" and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else conservation_programs.community_program_save(self, parts[2], body, parts[4]))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "program-applications" and method == "GET":
            return reply(conservation_programs.applications(self, parts[2]))
        if len(parts) == 5 and parts[:2] == ["api", "communities"] and parts[3] == "program-applications" and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else conservation_programs.review_application(self, parts[2], parts[4], body))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "contribution-reviews" and method == "GET":
            return reply(contribution_reviews.index(self, parts[2]))
        if len(parts) == 7 and parts[:2] == ["api", "communities"] and parts[3] == "contribution-reviews" and parts[6] == "decision" and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else contribution_reviews.decision(self, parts[2], parts[4], parts[5], body))
        if path == "/api/me/canvas" and method == "GET":
            return reply(creative_canvas.index(self))
        if path == "/api/me/canvas/candidates" and method == "GET":
            return reply(creative_canvas.candidate_list(self))
        if path == "/api/me/canvas/items" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else creative_canvas.post(self, body))
        if path == "/api/me/canvas/order" and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else creative_canvas.order(self, body))
        if len(parts) == 5 and parts[:4] == ["api", "me", "canvas", "items"]:
            if method == "GET": return reply(creative_canvas.detail(self, parts[4]))
            if method == "DELETE": return reply(creative_canvas.delete(self, parts[4]))

        if path == "/api/teacher/profile":
            if method == "GET": return reply(teacher_profile.get(self))
            if method == "PATCH":
                body, err = json_body(); return reply((400, err) if err else teacher_profile.patch(self, body))
        if path == "/api/teacher/profile/avatar" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else teacher_profile.upload(self, body))
        if path == "/api/teacher/avatar" and method == "GET":
            status, data, content_type, err = teacher_profile.image(self)
            if err: return reply((status, err))
            self._api_bytes(status, data, content_type); return True
        if path == "/api/public/profile":
            if method == "GET": return reply(public_profile.get(self))
            if method == "PATCH":
                body, err = json_body(); return reply((400, err) if err else public_profile.patch(self, body))
        if path == "/api/public/profile/avatar" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else public_profile.upload(self, body))
        if path == "/api/public/avatar" and method == "GET":
            status, data, content_type, err = public_profile.image(self)
            if err: return reply((status, err))
            self._api_bytes(status, data, content_type); return True

        if path == "/api/community/posts" and method == "GET": return reply(community.posts(self))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "library" and method == "GET":
            return reply(community_library.library(parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "public-profile" and method == "GET":
            return reply(community_library.community_profile(parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "community-members"] and parts[3] == "public-profile" and method == "GET":
            return reply(community_library.member_profile(parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "community-members"] and parts[3] == "contributions" and method == "GET":
            return reply(community_library.member_contributions(parts[2]))
        if path == "/api/communities" and method == "GET": return reply(community_portal.directory(self))
        if path == "/api/communities" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else community_portal.create(self, body))
        if path == "/api/me/communities" and method == "GET":
            return reply(community_portal.mine(self))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "join-requests" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else community_portal.join(self, parts[2], body))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "join-requests" and method == "GET":
            return reply(community_portal.requests(self, parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "member-candidates" and method == "GET":
            params = parse_qs(query); return reply(community_portal.candidates(self, parts[2], (params.get("q") or [""])[0]))
        if len(parts) == 3 and parts[:2] == ["api", "community-join-requests"] and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else community_portal.request_decision(self, parts[2], body))
        if len(parts) == 3 and parts[:2] == ["api", "communities"] and method == "GET":
            return reply(community_portal.workspace(self, parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "members" and method == "GET":
            return reply(community_portal.members(self, parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "communities"] and parts[3] == "members" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else community_portal.member_create(self, parts[2], body))
        if len(parts) == 4 and parts[:2] == ["api", "memberships"] and parts[3] == "role" and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else community_portal.member_role(self, parts[2], body))
        if len(parts) == 3 and parts[:2] == ["api", "memberships"] and method == "DELETE":
            return reply(community_portal.member_delete(self, parts[2]))
        if path == "/api/community/portal" and method == "GET": return reply(community_portal.directory(self))
        if len(parts) == 5 and parts[:3] == ["api", "community", "organisations"] and parts[4] == "join" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else community_portal.join(self, parts[3], body))
        if len(parts) == 4 and parts[:3] == ["api", "community", "organisations"] and method == "GET":
            return reply(community_portal.workspace(self, parts[3]))
        if len(parts) == 4 and parts[:3] == ["api", "community", "organisations"] and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else community_portal.workspace_update(self, parts[3], body))
        if len(parts) == 5 and parts[:3] == ["api", "community", "organisations"] and parts[4] == "cover":
            if method == "POST":
                body, err = json_body(); return reply((400, err) if err else community_portal.cover_upload(self, parts[3], body))
            if method == "DELETE":
                return reply(community_portal.cover_remove(self, parts[3]))
            if method == "GET":
                status, data, content_type, err = community_portal.cover_image(parts[3])
                if err: return reply((status, err))
                self._api_bytes(status, data, content_type); return True
        if len(parts) == 5 and parts[:3] == ["api", "community", "memberships"] and parts[4] == "role" and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else community_portal.member_role(self, parts[3], body))
        if path == "/api/notifications" and method == "GET": return reply(notifications.get(self))
        if path == "/api/notifications/read" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else notifications.read(self, body))
        if path == "/api/students/me/community-posts":
            if method == "GET": return reply(community.my_posts(self))
            if method == "POST":
                body, err = json_body(); return reply((400, err) if err else community.student_post(self, body))
        if path == "/api/students/me/community-images" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else community.student_image(self, body))
        if len(parts) == 5 and parts[:3] == ["api", "community", "posts"] and parts[4] == "comments" and method == "POST":
            body, err = json_body(); return reply((400, err) if err else community.comment(self, parts[3], body))
        if path == "/api/teacher/community-posts/pending" and method == "GET": return reply(community.teacher_pending(self))
        if len(parts) == 5 and parts[:3] == ["api", "teacher", "community-posts"] and parts[4] == "review" and method == "PATCH":
            body, err = json_body(); return reply((400, err) if err else community.teacher_review(self, parts[3], body))
        if len(parts) == 4 and parts[:3] == ["api", "community", "images"] and method == "GET":
            status, data, content_type, err = community.image(self, parts[3])
            if err: return reply((status, err))
            self._api_bytes(status, data, content_type); return True
        if len(parts) == 3 and parts[:2] == ["api", "learning-files"] and method == "GET":
            status, data, content_type, name, err = activity_file(self, parts[2])
            if err: return reply((status, err))
            self._api_bytes(status, data, content_type); return True
        if len(parts) == 3 and parts[:2] == ["api", "submission-files"] and method == "GET":
            status, data, content_type, err = submission_file(self, parts[2])
            if err: return reply((status, err))
            self._api_bytes(status, data, content_type); return True

        if parts[:3] == ["api", "students", "me"]:
            if len(parts) == 6 and parts[3] == "programs" and parts[5] == "materials" and method == "GET":
                return reply(student_work.list_materials(self, parts[4]))
            if len(parts) == 5 and parts[3] == "materials" and method == "GET":
                return reply(student_work.get_material(self, parts[4]))
            if len(parts) == 4 and parts[3] == "activities" and method == "GET":
                return reply(student_work.list_activities(self))
            if len(parts) == 5 and parts[3] == "activities" and method == "GET":
                return reply(student_work.get_activity(self, parts[4]))
            if len(parts) == 6 and parts[3] == "activities" and parts[5] == "submission":
                if method == "GET": return reply(student_work.get_submission(self, parts[4]))
                if method == "POST":
                    body, err = json_body()
                    return reply((400, err) if err else student_work.post_submission(self, parts[4], body))
            if len(parts) == 5 and parts[3] == "submissions" and method == "PATCH":
                body, err = json_body()
                return reply((400, err) if err else student_work.patch_submission(self, parts[4], body))
            if len(parts) == 6 and parts[3] == "submissions" and parts[5] == "feedback":
                if method == "GET": return reply(student_work.list_feedback(self, parts[4]))
                if method == "POST":
                    body, err = json_body(); return reply((400, err) if err else student_work.reply_feedback(self, parts[4], body))
            if len(parts) == 4 and parts[3] == "conversations":
                if method == "GET": return reply(student_work.list_conversations(self))
                if method == "POST":
                    body, err = json_body(); return reply((400, err) if err else student_work.create_conversation(self, body))
            if len(parts) == 6 and parts[3] == "conversations" and parts[5] == "messages":
                if method == "GET": return reply(student_work.get_messages(self, parts[4]))
                if method == "POST":
                    body, err = json_body(); return reply((400, err) if err else student_work.post_message(self, parts[4], body))
            if len(parts) == 6 and parts[3] == "conversations" and parts[5] == "read" and method == "POST":
                return reply(student_work.read_messages(self, parts[4]))
            if len(parts) == 4 and parts[3] == "progress" and method == "GET": return reply(student_work.get_progress(self))
            if len(parts) == 6 and parts[3] == "programs" and parts[5] == "progress" and method == "GET":
                return reply(student_work.get_program_progress(self, parts[4]))
            if len(parts) == 4 and parts[3] == "portfolio":
                if method == "GET": return reply(student_work.get_portfolio(self))
                if method == "POST":
                    body, err = json_body(); return reply((400, err) if err else student_work.post_portfolio(self, body))
            if len(parts) == 5 and parts[3] == "portfolio":
                if method == "PATCH":
                    body, err = json_body(); return reply((400, err) if err else student_work.patch_portfolio(self, parts[4], body))
                if method == "DELETE": return reply(student_work.delete_portfolio(self, parts[4]))
            if len(parts) == 6 and parts[3] == "submissions" and parts[5] == "library-status" and method == "GET":
                return reply(student_work.get_library_status(self, parts[4]))
            if len(parts) == 4 and parts[3] == "attachments" and method == "POST":
                body, err = json_body(); return reply((400, err) if err else student_work.upload_attachment(self, body))
            if len(parts) == 5 and parts[3] == "attachments" and method == "GET":
                status, data, content_type, err = student_work.attachment_bytes(self, parts[4])
                if err: return reply((status, err))
                self._api_bytes(status, data, content_type); return True

        if parts[:2] == ["api", "teacher"]:
            if len(parts) == 5 and parts[2] == "activities" and parts[4] == "submissions" and method == "GET":
                return reply(teacher_work.list_submissions(self, parts[3]))
            if len(parts) == 4 and parts[2] == "submissions" and method == "GET":
                return reply(teacher_work.get_submission(self, parts[3]))
            if len(parts) == 5 and parts[2] == "submissions" and parts[4] == "return" and method == "POST":
                body, err = json_body(); return reply((400, err) if err else teacher_work.return_student_submission(self, parts[3], body))
            if len(parts) == 5 and parts[2] == "submissions" and parts[4] == "feedback" and method == "POST":
                body, err = json_body(); return reply((400, err) if err else teacher_work.post_feedback(self, parts[3], body))
            if len(parts) == 4 and parts[2] == "feedback" and method == "PATCH":
                body, err = json_body(); return reply((400, err) if err else teacher_work.patch_feedback(self, parts[3], body))
            if len(parts) == 3 and parts[2] == "conversations":
                if method == "GET": return reply(teacher_work.list_conversations(self))
                if method == "POST":
                    body, err = json_body(); return reply((400, err) if err else teacher_work.create_conversation(self, body))
            if len(parts) == 5 and parts[2] == "conversations" and parts[4] == "messages":
                if method == "GET": return reply(teacher_work.get_messages(self, parts[3]))
                if method == "POST":
                    body, err = json_body(); return reply((400, err) if err else teacher_work.post_message(self, parts[3], body))
            if len(parts) == 5 and parts[2] == "conversations" and parts[4] == "read" and method == "POST":
                return reply(teacher_work.read_messages(self, parts[3]))
            if len(parts) == 5 and parts[2] == "classes" and parts[4] == "progress" and method == "GET":
                return reply(teacher_work.get_class_progress(self, parts[3]))
            if len(parts) == 5 and parts[2] == "students" and parts[4] == "progress" and method == "GET":
                return reply(teacher_work.get_student_progress(self, parts[3]))
            if len(parts) == 7 and parts[2] == "students" and parts[4] == "programs" and parts[6] == "report" and method == "GET":
                return reply(teacher_work.get_report(self, parts[3], parts[5]))
            if len(parts) == 5 and parts[2] == "submissions" and parts[4] == "library" and method == "PUT":
                body, err = json_body(); return reply((400, err) if err else teacher_work.put_library(self, parts[3], body))

        if path == "/api/auth/register" and method == "POST":
            try:
                body = self._read_body_json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._api_json(400, {"ok": False, "error": {"code": "INVALID_JSON", "message": "Invalid JSON."}})
                return True
            try:
                status, payload = handle_register(body or {})
            except Exception as exc:
                print(f"[register] {exc!r}")
                self._api_json(
                    500,
                    {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "Registration failed on server."}},
                )
                return True
            self._api_json(status, payload)
            return True

        if path == "/api/auth/login" and method == "POST":
            try:
                body = self._read_body_json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._api_json(400, {"ok": False, "error": {"code": "INVALID_JSON", "message": "Invalid JSON."}})
                return True
            # Use the TCP peer address. Do not trust X-Forwarded-For unless a
            # trusted reverse proxy is configured to replace it safely.
            status, payload, token = handle_login(body or {}, self.client_address[0])
            self._api_json(status, payload, set_cookie=token)
            return True

        if path == "/api/auth/logout" and method == "POST":
            status, payload, clear = handle_logout(self)
            self._api_json(status, payload, clear_cookie=clear)
            return True

        if path == "/api/auth/change-password" and method == "POST":
            try:
                body = self._read_body_json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._api_json(400, {"ok": False, "error": {"code": "INVALID_JSON", "message": "Invalid JSON."}})
                return True
            try:
                status, payload, clear = handle_change_password(self, body or {})
            except Exception as exc:
                print(f"[change-password] {exc!r}")
                self._api_json(500, {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "Password could not be changed."}})
                return True
            self._api_json(status, payload, clear_cookie=clear)
            return True

        if path == "/api/auth/me" and method == "GET":
            status, payload = handle_me(self)
            self._api_json(status, payload)
            return True

        if path == "/api/teacher/classes" and method == "GET":
            status, payload = handle_list_classes(self)
            self._api_json(status, payload)
            return True

        if path == "/api/teacher/classes" and method == "POST":
            try:
                body = self._read_body_json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._api_json(400, {"ok": False, "error": {"code": "INVALID_JSON", "message": "Invalid JSON."}})
                return True
            status, payload = handle_create_class(self, body or {})
            self._api_json(status, payload)
            return True

        if path.startswith("/api/teacher/classes/"):
            parts = [unquote(part) for part in path.strip("/").split("/")]
            class_id = parts[3] if len(parts) > 3 else ""
            if len(parts) == 4 and method == "GET":
                status, payload = handle_get_class(self, class_id)
                self._api_json(status, payload); return True
            if len(parts) == 4 and method == "PATCH":
                body, err = json_body()
                if err: self._api_json(400, err); return True
                status, payload = handle_patch_class(self, class_id, body)
                self._api_json(status, payload); return True
            if len(parts) == 5 and parts[4] == "students" and method == "GET":
                status, payload = handle_class_students(self, class_id)
                self._api_json(status, payload); return True
            if len(parts) == 6 and parts[4] == "students" and method == "DELETE":
                status, payload = handle_remove_student(self, class_id, parts[5])
                self._api_json(status, payload); return True
            if len(parts) == 5 and parts[4] in {"regenerate-code", "regenerate-access-code"} and method == "POST":
                status, payload = handle_regenerate_access_code(self, class_id)
                self._api_json(status, payload); return True

        if path.startswith("/api/teacher/classes/") and path.endswith("/regenerate-access-code") and method == "POST":
            class_id = unquote(
                path[len("/api/teacher/classes/") : -len("/regenerate-access-code")].strip("/")
            )
            status, payload = handle_regenerate_access_code(self, class_id)
            self._api_json(status, payload)
            return True

        if path == "/api/teacher/programs" and method == "GET":
            status, payload = list_programs(self); self._api_json(status, payload); return True
        if path == "/api/teacher/programs" and method == "POST":
            body, err = json_body()
            if err: self._api_json(400, err); return True
            status, payload = post_program(self, body); self._api_json(status, payload); return True
        if path == "/api/teacher/activity-attachments" and method == "POST":
            body, err = json_body()
            if err: self._api_json(400, err); return True
            status, payload = upload_activity_attachment(self, body); self._api_json(status, payload); return True
        if path.startswith("/api/teacher/programs/"):
            parts = [unquote(part) for part in path.strip("/").split("/")]
            program_id = parts[3] if len(parts) > 3 else ""
            if len(parts) == 4 and method == "GET": status, payload = get_program(self, program_id)
            elif len(parts) == 4 and method == "PATCH":
                body, err = json_body()
                if err: self._api_json(400, err); return True
                status, payload = patch_program(self, program_id, body)
            elif len(parts) == 5 and parts[4] == "classes" and method == "POST":
                body, err = json_body()
                if err: self._api_json(400, err); return True
                status, payload = program_classes(self, program_id, body)
            elif len(parts) == 5 and parts[4] == "status" and method == "PATCH":
                body, err = json_body()
                if err: self._api_json(400, err); return True
                status, payload = program_status(self, program_id, body)
            elif len(parts) == 5 and parts[4] == "materials" and method == "POST":
                body, err = json_body()
                if err: self._api_json(400, err); return True
                status, payload = post_material(self, program_id, body)
            elif len(parts) == 5 and parts[4] == "activities" and method == "POST":
                body, err = json_body()
                if err: self._api_json(400, err); return True
                status, payload = post_activity(self, program_id, body)
            else: return False
            self._api_json(status, payload); return True

        if path.startswith("/api/teacher/materials/"):
            parts = [unquote(part) for part in path.strip("/").split("/")]; material_id = parts[3]
            body, err = json_body()
            if err: self._api_json(400, err); return True
            if len(parts) == 4 and method == "PATCH": status, payload = patch_material(self, material_id, body)
            elif len(parts) == 5 and parts[4] == "status" and method == "PATCH": status, payload = material_status(self, material_id, body)
            else: return False
            self._api_json(status, payload); return True

        if path.startswith("/api/teacher/activities/"):
            parts = [unquote(part) for part in path.strip("/").split("/")]; activity_id = parts[3]
            body, err = json_body()
            if err: self._api_json(400, err); return True
            if len(parts) == 4 and method == "PATCH": status, payload = patch_activity(self, activity_id, body)
            elif len(parts) == 5 and parts[4] == "status" and method == "PATCH": status, payload = activity_status(self, activity_id, body)
            else: return False
            self._api_json(status, payload); return True

        if path == "/api/teacher/students" and method == "GET":
            status, payload = handle_list_students(self)
            self._api_json(status, payload)
            return True

        if path.startswith("/api/teacher/students/") and method == "GET":
            student_id = path.rsplit("/", 1)[-1]
            status, payload = handle_get_student(self, student_id)
            self._api_json(status, payload)
            return True

        if path == "/api/student/dashboard" and method == "GET":
            status, payload = student_dashboard(self)
            self._api_json(status, payload)
            return True

        if path == "/api/students/me/dashboard" and method == "GET":
            status, payload = student_learning_dashboard(self); self._api_json(status, payload); return True
        if path == "/api/students/me/programs" and method == "GET":
            status, payload = list_my_programs(self); self._api_json(status, payload); return True
        if path.startswith("/api/students/me/programs/") and method == "GET":
            program_id = unquote(path.rsplit("/", 1)[-1])
            status, payload = get_my_program(self, program_id); self._api_json(status, payload); return True

        if path == "/api/students/me/classes" and method == "GET":
            status, payload = handle_my_classes(self)
            self._api_json(status, payload)
            return True

        if path == "/api/students/me/profile" and method == "GET":
            status, payload = handle_my_profile(self)
            self._api_json(status, payload)
            return True

        if path == "/api/students/me/profile" and method == "PATCH":
            try:
                body = self._read_body_json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._api_json(400, {"ok": False, "error": {"code": "INVALID_JSON", "message": "Invalid JSON."}})
                return True
            status, payload = handle_patch_my_profile(self, body or {})
            self._api_json(status, payload)
            return True

        if path == "/api/students/me/profile/avatar" and method == "POST":
            try:
                body = self._read_body_json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._api_json(400, {"ok": False, "error": {"code": "INVALID_JSON", "message": "Invalid JSON."}})
                return True
            status, payload = handle_upload_avatar(self, body or {})
            self._api_json(status, payload)
            return True

        if path == "/api/students/me/avatar" and method == "GET":
            status, data, content_type, err = handle_get_avatar(self)
            if err:
                self._api_json(status, err)
                return True
            if data is not None and content_type:
                self._api_bytes(status, data, content_type)
                return True
            self.send_response(status)
            self.end_headers()
            return True

        if path == "/api/classes/join" and method == "POST":
            try:
                body = self._read_body_json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._api_json(400, {"ok": False, "error": {"code": "INVALID_JSON", "message": "Invalid JSON."}})
                return True
            status, payload = handle_join_class(self, body or {})
            self._api_json(status, payload)
            return True

        if path == "/api/health" and method == "GET":
            with connection() as conn:
                cursor = conn.cursor(); cursor.execute("SELECT 1"); cursor.fetchone(); cursor.close()
            self._api_json(
                200,
                {
                    "ok": True,
                    "storage": "mysql",
                    "database": "connected",
                },
            )
            return True

        if path == "/api/data" and method == "GET":
            data = read_document("komodo_hub")
            if not data:
                self.send_response(404)
                self.end_headers()
                return True
            self._api_json(200, data)
            return True

        if path == "/api/data" and method == "PUT":
            try:
                data = self._read_body_json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self.send_response(400)
                self.end_headers()
                return True
            if data is None or not isinstance(data, dict):
                self.send_response(400)
                self.end_headers()
                return True
            write_document("komodo_hub", data)
            replace_species(data.get("species") if isinstance(data.get("species"), list) else [])
            self._api_json(200, {"ok": True})
            return True

        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        parsed = urlparse(self.path)
        if self._dispatch_api("GET", parsed.path, parsed.query):
            return
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if self._dispatch_api("POST", path):
            return
        self.send_response(404)
        self.end_headers()

    def do_PUT(self):
        path = urlparse(self.path).path
        if self._dispatch_api("PUT", path):
            return
        self.send_response(404)
        self.end_headers()

    def do_PATCH(self):
        path = urlparse(self.path).path
        if self._dispatch_api("PATCH", path):
            return
        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        path = urlparse(self.path).path
        if self._dispatch_api("DELETE", path):
            return
        self.send_response(404)
        self.end_headers()


def main():
    initialize_database()
    create_schema()
    seed_users_if_empty()
    seed_admin_user_if_missing()
    seed_public_users_if_missing()
    seed_classes_if_empty()
    seed_enrollments_if_empty()
    if not STATIC_DIR.is_dir():
        raise SystemExit(f"Static folder not found: {STATIC_DIR}")
    print("Komodo Hub API + static server")
    print(f"  UI:    http://{HOST}:{PORT}/")
    print("  Store: MySQL")
    httpd = ThreadingHTTPServer((HOST, PORT), KomodoHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
