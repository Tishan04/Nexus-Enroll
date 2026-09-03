import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common.domain.models import ChangeRequestStatus, UserRole

app = FastAPI(title="NexusEnroll Administrator Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

IDENTITY_SERVICE_URL = os.getenv(
    "IDENTITY_URL", "http://localhost:8001"
)
ENROLLMENT_SERVICE_URL = os.getenv(
    "ENROLLMENT_URL", "http://localhost:8002"
)
FACULTY_SERVICE_URL = os.getenv(
    "FACULTY_URL", "http://localhost:8003"
)
http_client = httpx.Client()

class UserPatch(BaseModel):
    active: bool | None = None
    name: str | None = None
    email: str | None = None

class UserCreate(BaseModel):
    user_id: str
    name: str
    email: str
    role: UserRole
    department: str = ""

class OverrideIn(BaseModel):
    student_id: str
    offering_id: str

def get_json(path: str, service_url: str):
    response = http_client.get(f"{service_url}{path}", timeout=2)
    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text)
    return response.json()

def require_admin(admin_id: str):
    administrator = get_json(
        f"/users/{admin_id}", IDENTITY_SERVICE_URL
    )
    if (
        administrator["role"] != "administrator"
        or not administrator["active"]
    ):
        raise HTTPException(403, "Administrator access required")


@app.get("/health")
def health():
    return {"status": "ok", "service": "admin"}


@app.post("/users", status_code=201)
def create_user(admin_id: str, body: UserCreate):
    require_admin(admin_id)
    response = http_client.post(
        f"{IDENTITY_SERVICE_URL}/users",
        json=body.model_dump(),
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.patch("/users/{user_id}")
def update_user(user_id: str, admin_id: str, body: UserPatch):
    require_admin(admin_id)
    response = http_client.patch(
        f"{IDENTITY_SERVICE_URL}/users/{user_id}",
        json=body.model_dump(exclude_none=True),
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.post("/courses")
def create_course(admin_id: str, body: dict):
    require_admin(admin_id)
    response = http_client.post(
        f"{ENROLLMENT_SERVICE_URL}/courses",
        json=body,
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.delete("/courses/{code}")
def delete_course(admin_id: str, code: str):
    require_admin(admin_id)
    response = http_client.delete(
        f"{ENROLLMENT_SERVICE_URL}/courses/{code}", timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.post("/offerings")
def create_offering(admin_id: str, body: dict):
    require_admin(admin_id)
    response = http_client.post(
        f"{ENROLLMENT_SERVICE_URL}/offerings",
        json=body,
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.post("/programs")
def create_program(admin_id: str, body: dict):
    require_admin(admin_id)
    response = http_client.post(
        f"{ENROLLMENT_SERVICE_URL}/programs",
        json=body,
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.post("/enrollments/override")
def override_enrollment(admin_id: str, body: OverrideIn):
    require_admin(admin_id)
    response = http_client.post(
        f"{ENROLLMENT_SERVICE_URL}/internal/override",
        json=body.model_dump(),
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.post("/grades/{submission_id}/approve")
def approve_grade(admin_id: str, submission_id: str):
    require_admin(admin_id)
    response = http_client.post(
        f"{FACULTY_SERVICE_URL}/internal/grades/{submission_id}/approve",
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.post("/grades/{submission_id}/reject")
def reject_grade(admin_id: str, submission_id: str, reason: str):
    require_admin(admin_id)
    response = http_client.post(
        f"{FACULTY_SERVICE_URL}/internal/grades/{submission_id}/reject",
        params={"reason": reason},
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.post("/course-changes/{request_id}/approve")
def approve_course_change(admin_id: str, request_id: str):
    require_admin(admin_id)
    response = http_client.post(
        f"{FACULTY_SERVICE_URL}/internal/course-changes/{request_id}/approve",
        timeout=2
    )
    response.raise_for_status()
    return response.json()


@app.get("/reports/enrolment")
def enrollment_report(admin_id: str):
    require_admin(admin_id)
    students = get_json("/users?role=student", IDENTITY_SERVICE_URL)
    offerings = get_json("/courses", ENROLLMENT_SERVICE_URL)

    course_data = [
        {
            "code": item["code"],
            "offering": item["offering"]["offering_id"],
            "occupancy": (
                item["offering"]["capacity"]
                - item["offering"]["available_seats"]
            ),
            "capacity": item["offering"]["capacity"],
        }
        for item in offerings
    ]
    return {
        "students": len(students),
        "course_offerings": len(offerings),
        "courses": course_data
    }


@app.get("/reports/faculty-workload")
def faculty_workload_report(admin_id: str):
    require_admin(admin_id)
    faculty_members = get_json(
        "/users?role=faculty", IDENTITY_SERVICE_URL
    )
    offerings = get_json("/courses", ENROLLMENT_SERVICE_URL)

    return [
        {
            "faculty_id": faculty["user_id"],
            "name": faculty["name"],
            "offerings": len(
                [
                    item
                    for item in offerings
                    if item["offering"]["faculty_id"] == faculty["user_id"]
                ]
            ),
        }
        for faculty in faculty_members
    ]

@app.get("/reports/course-popularity")
def course_popularity_report(admin_id: str):
    require_admin(admin_id)
    offerings = get_json("/courses", ENROLLMENT_SERVICE_URL)

    report = [
        {
            "course_code": item["code"],
            "offering_id": item["offering"]["offering_id"],
            "enrolled": (
                item["offering"]["capacity"]
                - item["offering"]["available_seats"]
            ),
            "capacity": item["offering"]["capacity"]
        }
        for item in offerings
    ]
    return sorted(report, key=lambda item: item["enrolled"], reverse=True)
