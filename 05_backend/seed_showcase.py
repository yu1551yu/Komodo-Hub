from __future__ import annotations

import shutil
from pathlib import Path

from models.json_store import read_rows, write_rows


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
NOW = "2026-10-07T09:00:00+00:00"
TEACHER = "usr_demo_teacher"
STUDENT = "usr_demo_student"
CLASS = "class_showcase_coast"
PROGRAM = "program_showcase_coast"


def write_field_guide_pdf(path: Path) -> None:
    lines = [
        "Komodo Hub - Coastal Field Observation Guide",
        "1. Observe wildlife from a safe distance.",
        "2. Record date, time, weather and habitat conditions.",
        "3. Photograph evidence without disturbing plants or animals.",
        "4. Do not publish sensitive nest or den locations.",
        "5. Explain one practical action that could protect the habitat.",
    ]
    commands = ["BT", "/F1 18 Tf", "72 750 Td", f"({lines[0]}) Tj", "/F1 11 Tf"]
    for line in lines[1:]:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.extend(["0 -34 Td", f"({safe}) Tj"])
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.write_bytes(output)


def seed_files() -> list[dict]:
    target = DATA / "activity_attachments"
    target.mkdir(parents=True, exist_ok=True)
    image_id = "activity_file_showcase_map"
    pdf_id = "activity_file_showcase_guide"
    shutil.copyfile(ROOT.parent / "komodo-hub-react" / "src" / "assets" / "hero.png", target / f"{image_id}.png")
    write_field_guide_pdf(target / f"{pdf_id}.pdf")
    return [
        {"id": image_id, "name": "coastal-observation-map.png", "contentType": "image/png", "size": (target / f"{image_id}.png").stat().st_size, "url": f"/api/learning-files/{image_id}"},
        {"id": pdf_id, "name": "field-observation-guide.pdf", "contentType": "application/pdf", "size": (target / f"{pdf_id}.pdf").stat().st_size, "url": f"/api/learning-files/{pdf_id}"},
    ]


def main() -> None:
    attachments = seed_files()
    users = read_rows("users.json")
    for user in users:
        if user.get("role") == "TEACHER":
            user["teacherClassIds"] = [CLASS] if user.get("id") == TEACHER else []
    write_rows("users.json", users)

    write_rows("classes.json", [{
        "id": CLASS, "name": "Coastal Conservation Lab", "description": "A complete demo class for testing the Komodo Hub learning workflow.",
        "grade": "Grade 5", "teacherId": TEACHER, "accessCode": "COAST-2026", "accessCodeExpiresAt": None,
        "createdAt": NOW, "updatedAt": NOW,
    }])
    write_rows("enrollments.json", [{"id": "enrollment_showcase", "studentId": STUDENT, "classId": CLASS, "joinedAt": NOW}])
    write_rows("programs.json", [{
        "id": PROGRAM, "title": "Coastal Biodiversity Field Study",
        "description": "Observe a coastal habitat, identify signs of biodiversity and communicate evidence responsibly.",
        "learningObjectives": "Identify species and habitat evidence; record observations safely; explain one practical conservation action.",
        "teacherId": TEACHER, "status": "published", "createdAt": NOW, "updatedAt": NOW,
    }])
    write_rows("program_classes.json", [{"id": "program_class_showcase", "programId": PROGRAM, "classId": CLASS, "createdAt": NOW, "updatedAt": NOW}])
    write_rows("materials.json", [
        {"id": "material_showcase_1", "programId": PROGRAM, "title": "How to write a field observation", "description": "Record what you can see, where you saw it and why it may matter. Avoid disturbing wildlife or revealing sensitive nest locations.", "resourceType": "teacher-note", "resourceRef": "", "sourceContentId": None, "attachments": [], "status": "published", "position": 0, "createdBy": TEACHER, "createdAt": NOW, "updatedAt": NOW},
        {"id": "material_showcase_2", "programId": PROGRAM, "title": "Coastal survey checklist", "description": "Use this checklist before starting the photo survey Activity.", "resourceType": "file", "resourceRef": "", "sourceContentId": None, "attachments": [attachments[1]], "status": "published", "position": 1, "createdBy": TEACHER, "createdAt": NOW, "updatedAt": NOW},
    ])
    write_rows("learning_activities.json", [
        {"id": "activity_showcase_reviewed", "programId": PROGRAM, "title": "Habitat evidence note", "description": "Describe one sign that this habitat supports wildlife.", "instructions": "Write 100-150 words. Include the habitat feature, the evidence you observed and one conservation action.", "activityType": "classroom", "dueDate": "2026-10-15", "attachments": [], "status": "published", "createdBy": TEACHER, "createdAt": NOW, "updatedAt": NOW},
        {"id": "activity_showcase_upload", "programId": PROGRAM, "title": "Coastal photo survey", "description": "Upload photos or files from a safe observation point.", "instructions": "Open the map and field guide below. Upload up to five photos or documents, then explain what each item shows. Save a draft first if your observation is incomplete.", "activityType": "outdoor", "dueDate": "2026-10-20", "attachments": attachments, "status": "published", "createdBy": TEACHER, "createdAt": NOW, "updatedAt": NOW},
        {"id": "activity_showcase_closed", "programId": PROGRAM, "title": "Practice species quiz", "description": "A closed example Activity for checking status behaviour.", "instructions": "This Activity is closed, so new submissions are unavailable.", "activityType": "classroom", "dueDate": None, "attachments": [], "status": "closed", "createdBy": TEACHER, "createdAt": NOW, "updatedAt": NOW},
    ])
    write_rows("submissions.json", [{
        "id": "submission_showcase_reviewed", "activityId": "activity_showcase_reviewed", "studentId": STUDENT,
        "content": "Mangrove roots trap sediment and create shelter for juvenile fish and small crabs. I observed tracks and feeding marks close to the roots. A useful conservation action is to keep litter away from the tidal edge and record observations without stepping on new mangrove growth.",
        "notes": "Completed during the class observation exercise.", "submissionType": "file", "attachments": [],
        "status": "reviewed", "submittedAt": "2026-10-06T10:20:00+00:00", "createdAt": "2026-10-06T10:20:00+00:00", "updatedAt": "2026-10-06T11:00:00+00:00",
    }])
    write_rows("feedback.json", [{
        "id": "feedback_showcase", "submissionId": "submission_showcase_reviewed", "teacherId": TEACHER, "studentId": STUDENT,
        "authorId": TEACHER, "authorRole": "TEACHER", "parentFeedbackId": None,
        "content": "Clear evidence and a realistic conservation action. In your next survey, add the time and weather conditions.",
        "createdAt": "2026-10-06T11:00:00+00:00", "updatedAt": "2026-10-06T11:00:00+00:00",
    }])
    write_rows("portfolio_items.json", [{"id": "portfolio_showcase", "studentId": STUDENT, "submissionId": "submission_showcase_reviewed", "displayOrder": 0, "caption": "Mangrove habitat evidence", "createdAt": NOW, "updatedAt": NOW}])
    write_rows("conversations.json", [{"id": "conversation_showcase", "teacherId": TEACHER, "studentId": STUDENT, "createdAt": "2026-10-06T08:00:00+00:00", "updatedAt": "2026-10-06T08:15:00+00:00"}])
    write_rows("messages.json", [
        {"id": "message_showcase_1", "conversationId": "conversation_showcase", "senderId": TEACHER, "content": "Please remember to observe from a safe distance and use the field guide.", "readAt": "2026-10-06T08:05:00+00:00", "createdAt": "2026-10-06T08:00:00+00:00", "updatedAt": "2026-10-06T08:05:00+00:00"},
        {"id": "message_showcase_2", "conversationId": "conversation_showcase", "senderId": STUDENT, "content": "I will save the photo survey as a draft before submitting it.", "readAt": "2026-10-06T08:15:00+00:00", "createdAt": "2026-10-06T08:10:00+00:00", "updatedAt": "2026-10-06T08:15:00+00:00"},
    ])
    write_rows("community_posts.json", [{
        "id": "post_showcase", "title": "Mangrove roots after the morning tide", "content": "The exposed roots held small shells and showed signs of crab activity. The area was observed without entering the young mangrove patch.",
        "species": "Mangrove crab", "place": "Coastal study zone", "attachment": None, "createdBy": STUDENT,
        "authorRole": "STUDENT", "status": "approved", "reviewedBy": TEACHER, "reviewedAt": "2026-10-06T12:00:00+00:00",
        "createdAt": "2026-10-06T11:30:00+00:00", "updatedAt": "2026-10-06T12:00:00+00:00", "reviewNote": "Approved for the class community feed.",
    }])
    write_rows("community_comments.json", [{"id": "comment_showcase", "postId": "post_showcase", "userId": TEACHER, "authorName": "Bu Sari", "authorRole": "TEACHER", "content": "Good field ethics and a useful observation.", "createdAt": "2026-10-06T12:10:00+00:00", "updatedAt": "2026-10-06T12:10:00+00:00"}])
    write_rows("notifications.json", [{"id": "notification_showcase", "userId": STUDENT, "kind": "activity", "title": "New activity published", "message": "Coastal photo survey", "resourceId": "activity_showcase_upload", "readAt": None, "createdAt": NOW, "updatedAt": NOW}])
    write_rows("library_items.json", [])
    print("Showcase data created for teacher@komodo.id and student@komodo.id")


if __name__ == "__main__":
    main()
