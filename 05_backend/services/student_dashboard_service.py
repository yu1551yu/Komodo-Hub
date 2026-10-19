from __future__ import annotations

from services.enrollment_service import student_classes
from services.program_service import student_program, student_programs
from services.progress_service import student_progress
from services.student_work_service import FEEDBACK, SUBMISSIONS
from models.work_repository import list_rows


def dashboard(student_id: str) -> dict:
    _, class_payload = student_classes(student_id)
    programs = student_programs(student_id)
    activities = []
    for program in programs:
        detail = student_program(student_id, program["id"])
        activities.extend(detail["activities"])
    activities.sort(key=lambda row: row.get("updatedAt", ""), reverse=True)
    submission_ids = {row["id"] for row in list_rows(SUBMISSIONS) if row.get("studentId") == student_id}
    feedback = [row for row in list_rows(FEEDBACK) if row.get("submissionId") in submission_ids and row.get("authorRole") == "TEACHER"]
    progress = student_progress(student_id)
    return {"classes": class_payload.get("data", {}).get("classes", []), "programs": programs, "recentActivities": activities[:5], "pendingActivityCount": progress["remainingActivities"], "recentFeedback": feedback[-3:], "progress": {"completed": progress["completedActivities"], "total": progress["totalActivities"], "percentage": progress["percentage"]}}
