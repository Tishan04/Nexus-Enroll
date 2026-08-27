import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common.domain.models import (
    ChangeRequestStatus,
    CourseChangeRequest,
    GradeSubmission,
)
from common.patterns.observer import (
    DomainEvent,
    EventPublisher,
    HttpNotificationObserver,
)
from common.patterns.state import get_grade_state
from common.repositories.memory import ChangeRepository, GradeRepository


app = FastAPI(title="NexusEnroll Faculty Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IDENTITY_SERVICE_URL = os.getenv(
    "IDENTITY_URL", "http://localhost:8001"
)
ENROLLMENT_SERVICE_URL = os.getenv(
    "ENROLLMENT_URL", "http://localhost:8002"
)
NOTIFICATION_SERVICE_URL = os.getenv(
    "NOTIFICATION_URL", "http://localhost:8005"
)

http_client = httpx.Client()
grade_repository = GradeRepository()
change_repository = ChangeRepository()
event_publisher = EventPublisher()
event_publisher.subscribe(
    HttpNotificationObserver(http_client, NOTIFICATION_SERVICE_URL)
)
VALID_GRADES = {
    "A+",
    "A",
    "A-",
    "B+",
    "B",
    "B-",
    "C+",
    "C",
    "C-",
    "D",
    "F",
}


class GradeIn(BaseModel):
    faculty_id: str
    student_id: str
    offering_id: str
    grade: str


class BatchGrades(BaseModel):
    faculty_id: str
    offering_id: str
    grades: dict[str, str]


class ChangeIn(BaseModel):
    faculty_id: str
    course_code: str
    action: str
    payload: dict
    description: str


def get_json(path: str, service_url: str):
    response = http_client.get(f"{service_url}{path}", timeout=2)
    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text)
    return response.json()


def require_faculty(faculty_id: str):
    faculty = get_json(
        f"/users/{faculty_id}", IDENTITY_SERVICE_URL
    )
    if faculty["role"] != "faculty" or not faculty["active"]:
        raise HTTPException(403, "Faculty access required")
    return faculty


@app.get("/health")
def health():
    return {"status": "ok", "service": "faculty"}


@app.get("/rosters/{faculty_id}/{offering_id}")
def get_roster(faculty_id: str, offering_id: str):
    require_faculty(faculty_id)
    offering = get_json(
        f"/offerings/{offering_id}", ENROLLMENT_SERVICE_URL
    )
    if offering["faculty_id"] != faculty_id:
        raise HTTPException(
            403, "Offering is not assigned to this faculty member"
        )
    return get_json(
        f"/internal/roster/{offering_id}", ENROLLMENT_SERVICE_URL
    )


@app.post("/grades")
def submit_grade(body: GradeIn):
    require_faculty(body.faculty_id)
    if body.grade.upper() not in VALID_GRADES:
        raise HTTPException(400, "Invalid grade")

    roster = get_json(
        f"/internal/roster/{body.offering_id}", ENROLLMENT_SERVICE_URL
    )
    enrolled_student_ids = {
        student["user_id"] for student in roster["students"]
    }
    if body.student_id not in enrolled_student_ids:
        raise HTTPException(400, "Student is not enrolled")

    grade_submission = GradeSubmission(
        body.faculty_id,
        body.student_id,
        body.offering_id,
        body.grade.upper(),
    )
    get_grade_state(grade_submission).submit(grade_submission)
    grade_repository.save(grade_submission)
    return grade_submission.__dict__


@app.post("/grades/batch")
def submit_batch_grades(body: BatchGrades):
    accepted_grades = []
    rejected_grades = {}

    for student_id, grade in body.grades.items():
        try:
            accepted_grades.append(
                submit_grade(
                    GradeIn(
                        faculty_id=body.faculty_id,
                        student_id=student_id,
                        offering_id=body.offering_id,
                        grade=grade,
                    )
                )
            )
        except HTTPException as exc:
            rejected_grades[student_id] = exc.detail

    return {"accepted": accepted_grades, "rejected": rejected_grades}


@app.get("/grades")
def list_grades(faculty_id: str | None = None):
    return [
        grade.__dict__
        for grade in grade_repository.all()
        if faculty_id is None or grade.faculty_id == faculty_id
    ]


@app.post("/course-changes", status_code=201)
def request_course_change(body: ChangeIn):
    require_faculty(body.faculty_id)
    change_request = CourseChangeRequest(
        body.faculty_id,
        body.course_code,
        body.action,
        body.payload,
        body.description,
    )
    change_repository.save(change_request)
    return change_request.__dict__


@app.get("/course-changes")
def list_course_changes(status: ChangeRequestStatus | None = None):
    return [
        change.__dict__
        for change in change_repository.all()
        if status is None or change.status == status
    ]


@app.post("/internal/grades/{submission_id}/approve")
def approve_grade(submission_id: str):
    grade_submission = grade_repository.get(submission_id)
    if not grade_submission:
        raise HTTPException(404, "Grade not found")

    get_grade_state(grade_submission).approve(grade_submission)
    grade_repository.save(grade_submission)

    offering = get_json(
        f"/offerings/{grade_submission.offering_id}", ENROLLMENT_SERVICE_URL
    )
    response = http_client.put(
        f"{IDENTITY_SERVICE_URL}/students/"
        f"{grade_submission.student_id}/completed-courses/"
        f"{offering['course_code']}",
        params={"grade": grade_submission.grade},
        timeout=2,
    )
    response.raise_for_status()

    event_publisher.publish(
        DomainEvent(
            "grade_submitted",
            {
                "submission_id": grade_submission.submission_id,
                "student_id": grade_submission.student_id,
            },
        )
    )
    return grade_submission.__dict__


@app.post("/internal/grades/{submission_id}/reject")
def reject_grade(submission_id: str, reason: str):
    grade_submission = grade_repository.get(submission_id)
    if not grade_submission:
        raise HTTPException(404, "Grade not found")

    get_grade_state(grade_submission).reject(grade_submission, reason)
    grade_repository.save(grade_submission)
    return grade_submission.__dict__


@app.post("/internal/course-changes/{request_id}/approve")
def approve_course_change(request_id: str):
    change_request = change_repository.get(request_id)
    if (
        not change_request
        or change_request.status != ChangeRequestStatus.PENDING
    ):
        raise HTTPException(
            400, "Only pending request can be approved"
        )

    response = http_client.post(
        f"{ENROLLMENT_SERVICE_URL}/internal/course-changes/execute",
        json={
            "action": change_request.action,
            "payload": change_request.payload,
        },
        timeout=2,
    )
    response.raise_for_status()

    change_request.status = ChangeRequestStatus.APPROVED
    change_repository.save(change_request)
    event_publisher.publish(
        DomainEvent(
            "course_change_approved",
            {"request_id": request_id},
        )
    )
    return change_request.__dict__
