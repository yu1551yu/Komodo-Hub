"""Read-only review reminders using the existing submission and access models."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models.user_repository import find_by_id as find_user
from models.work_repository import list_rows
from services.learning_access_service import AccessError, require_teacher_submission_relationship

REVIEW_LIMIT_HOURS = 24


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def review_state(submission: dict, now: datetime | None = None) -> dict:
    now = now or utc_now()
    pending = submission.get("status") == "submitted"
    result = {"pending": pending, "overdue": False, "dueAt": None,
              "waitingSeconds": None, "timingAvailable": False}
    if not pending:
        return result
    try:
        submitted = datetime.fromisoformat(submission["submittedAt"])
        # Existing submission timestamps include a timezone. Do not guess one
        # for malformed legacy data, or substitute draft creation/update time.
        if submitted.tzinfo is None:
            return result
        due = submitted + timedelta(hours=REVIEW_LIMIT_HOURS)
    except (KeyError, TypeError, ValueError, OverflowError):
        return result
    return {**result, "overdue": now > due, "dueAt": due.isoformat(),
            "waitingSeconds": max(0, int((now - submitted).total_seconds())),
            "timingAvailable": True}


def with_review_state(submission: dict, now: datetime | None = None) -> dict:
    return {**submission, "review": review_state(submission, now)}


def teacher_review_summary(teacher_id: str, now: datetime | None = None) -> dict:
    now = now or utc_now()
    items = []
    for row in list_rows("submissions.json"):
        if row.get("status") != "submitted":
            continue
        try:
            activity = require_teacher_submission_relationship(teacher_id, row)
        except AccessError:
            continue
        student = find_user(row["studentId"]) or {}
        items.append({"id": row["id"], "activityId": activity["id"],
                      "activityTitle": activity.get("title", "Activity"),
                      "student": {"id": row["studentId"], "name": student.get("name", "Student")},
                      "submittedAt": row.get("submittedAt"), "review": review_state(row, now)})
    items.sort(key=lambda item: (not item["review"]["overdue"],
                                -(item["review"]["waitingSeconds"] or 0), item["id"]))
    return {"thresholdHours": REVIEW_LIMIT_HOURS, "pendingCount": len(items),
            "overdueCount": sum(item["review"]["overdue"] for item in items),
            "checkedAt": now.isoformat(), "items": items}
