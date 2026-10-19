from __future__ import annotations

from models.class_repository import find_by_id as find_class
from models.enrollment_repository import list_for_student, list_student_ids_for_class
from models.learning_activity_repository import list_for_program
from models.program_class_repository import program_ids_for_classes
from models.program_repository import find_by_id as find_program
from models.user_repository import find_by_id as find_user
from models.work_repository import list_rows
from services.learning_access_service import require_student_program, require_teacher_student
from services.ownership_service import owned_class
from services.student_work_service import FEEDBACK, SUBMISSIONS


def _program_progress(student_id: str, program_id: str) -> dict:
    program = require_student_program(student_id, program_id)
    activities = [row for row in list_for_program(program_id) if row.get("status") in {"published", "closed"}]
    submissions = {row["activityId"]: row for row in list_rows(SUBMISSIONS) if row.get("studentId") == student_id and row.get("activityId") in {a["id"] for a in activities} and row.get("status") in {"submitted", "reviewed"}}
    completed = [activity for activity in activities if activity["id"] in submissions]
    total = len(activities)
    recent = sorted([{"activityId": row["activityId"], "submissionId": row["id"], "status": row.get("status"), "submittedAt": row.get("submittedAt")} for row in submissions.values()], key=lambda row: row.get("submittedAt") or "", reverse=True)[:5]
    return {"programId": program_id, "programTitle": program.get("title"), "totalActivities": total, "completedActivities": len(completed), "remainingActivities": total - len(completed), "reviewedActivities": len([row for row in submissions.values() if row.get("status") == "reviewed"]), "percentage": round(len(completed) * 100 / total) if total else 0, "recentCompletions": recent}


def student_program_progress(student_id: str, program_id: str) -> dict:
    return _program_progress(student_id, program_id)


def student_progress(student_id: str) -> dict:
    class_ids = [row["classId"] for row in list_for_student(student_id)]
    programs = []
    for program_id in program_ids_for_classes(class_ids):
        program = find_program(program_id)
        if program and program.get("status") == "published":
            programs.append(_program_progress(student_id, program_id))
    total = sum(row["totalActivities"] for row in programs)
    completed = sum(row["completedActivities"] for row in programs)
    return {"programs": programs, "totalActivities": total, "completedActivities": completed, "remainingActivities": total - completed, "percentage": round(completed * 100 / total) if total else 0}


def teacher_class_progress(teacher_id: str, class_id: str) -> dict:
    class_row = owned_class(teacher_id, class_id)
    students = []
    submissions = list_rows(SUBMISSIONS)
    for student_id in list_student_ids_for_class(class_id):
        user = find_user(student_id) or {}
        progress = student_progress(student_id)
        latest = max((row for row in submissions if row.get("studentId") == student_id), key=lambda row: row.get("submittedAt") or "", default=None)
        students.append({"studentId": student_id, "studentName": user.get("name", "Student"), "programs": progress["programs"], "completedActivities": progress["completedActivities"], "totalActivities": progress["totalActivities"], "percentage": progress["percentage"], "lastSubmission": latest})
    return {"class": {"id": class_row["id"], "name": class_row.get("name")}, "students": students}


def teacher_student_progress(teacher_id: str, student_id: str) -> dict:
    class_ids = require_teacher_student(teacher_id, student_id)
    user = find_user(student_id) or {}
    return {"student": {"id": student_id, "name": user.get("name", "Student")}, "classes": [{"id": cid, "name": (find_class(cid) or {}).get("name")} for cid in class_ids], **student_progress(student_id)}


def teacher_student_report(teacher_id: str, student_id: str, program_id: str) -> dict:
    from models.json_store import now_iso
    require_teacher_student(teacher_id, student_id)
    from services.ownership_service import owned_program
    owned_program(teacher_id, program_id)
    progress = _program_progress(student_id, program_id)
    submissions = [row for row in list_rows(SUBMISSIONS) if row.get("studentId") == student_id and (find_program(program_id) and row.get("activityId") in {a["id"] for a in list_for_program(program_id)})]
    submission_ids = {row["id"] for row in submissions}
    feedback = [row for row in list_rows(FEEDBACK) if row.get("submissionId") in submission_ids and row.get("authorRole") == "TEACHER"]
    user = find_user(student_id) or {}
    student_classes = [find_class(row["classId"]) for row in list_for_student(student_id)]
    classes = [row for row in student_classes if row and row.get("teacherId") == teacher_id]
    return {"studentDisplayName": user.get("name", "Student"), "classes": [row.get("name") for row in classes], "program": progress["programTitle"], "activitiesCompleted": progress["completedActivities"], "activitiesPending": progress["remainingActivities"], "overallProgressPercentage": progress["percentage"], "submissionHistory": [{"id": row["id"], "status": row.get("status"), "submittedAt": row.get("submittedAt")} for row in submissions], "feedbackSummary": [row.get("content") for row in feedback[-5:]], "generatedAt": now_iso()}
