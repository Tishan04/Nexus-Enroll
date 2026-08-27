import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from common.domain.models import (
    Course,
    CourseOffering,
    DegreeProgram,
    Enrollment,
    EnrollmentStatus,
    Student,
    TimeSlot,
    UserRole,
    ValidationFailure,
)
from common.patterns.command import build_course_change_command
from common.patterns.observer import (
    DomainEvent,
    EventPublisher,
    HttpNotificationObserver,
)
from common.patterns.validation import build_enrollment_validation_chain
from common.repositories.memory import (
    CourseRepository,
    EnrollmentRepository,
    ProgramRepository,
    ScheduleRepository,
    UnitOfWork,
)


app = FastAPI(title="NexusEnroll Enrollment Service", version="1.0.0")
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
NOTIFICATION_SERVICE_URL = os.getenv(
    "NOTIFICATION_URL", "http://localhost:8005"
)

course_repository = CourseRepository()
program_repository = ProgramRepository()
enrollment_repository = EnrollmentRepository()
schedule_repository = ScheduleRepository()
event_publisher = EventPublisher()
unit_of_work = UnitOfWork(
    [course_repository, enrollment_repository, schedule_repository]
)
http_client = httpx.Client()
event_publisher.subscribe(
    HttpNotificationObserver(http_client, NOTIFICATION_SERVICE_URL)
)
enrollment_validator = build_enrollment_validation_chain(
    course_repository, schedule_repository
)


class SlotIn(BaseModel):
    day: str
    start_minute: int
    end_minute: int
    location: str


class CourseIn(BaseModel):
    code: str
    name: str
    description: str
    department: str
    prerequisites: list[str] = Field(default_factory=list)


class OfferingIn(BaseModel):
    offering_id: str
    course_code: str
    semester: str
    faculty_id: str
    capacity: int = Field(gt=0)
    slots: list[SlotIn] = Field(default_factory=list)


class ProgramIn(BaseModel):
    program_code: str
    name: str
    required_courses: list[str] = Field(default_factory=list)
    critical_courses: list[str] = Field(default_factory=list)


class EnrollmentIn(BaseModel):
    student_id: str
    offering_id: str


class ChangeExecute(BaseModel):
    action: str
    payload: dict


def get_identity_data(path: str):
    try:
        response = http_client.get(
            f"{IDENTITY_SERVICE_URL}{path}", timeout=2
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            503, f"Identity service unavailable: {exc}"
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text)
    return response.json()


def seed_courses_and_program():
    course_repository.save_course(
        Course(
            "CS1201",
            "Programming Fundamentals",
            "Programming basics",
            "Computer Science",
        )
    )
    course_repository.save_course(
        Course(
            "CS2303",
            "Software Architecture",
            "Architecture, principles and design patterns",
            "Computer Science",
            {"CS1201"},
        )
    )
    course_repository.save_course(
        Course(
            "CS2306",
            "Computer Networks",
            "Networking fundamentals",
            "Computer Science",
        )
    )
    course_repository.save_offering(
        CourseOffering(
            "CS2303-2026S1",
            "CS2303",
            "2026-S1",
            "F001",
            2,
            [TimeSlot("Monday", 540, 660, "Lab 01")],
        )
    )
    course_repository.save_offering(
        CourseOffering(
            "CS2306-2026S1",
            "CS2306",
            "2026-S1",
            "F001",
            30,
            [TimeSlot("Monday", 600, 720, "Lab 02")],
        )
    )
    program_repository.save(
        DegreeProgram(
            "BCS",
            "BSc Computer Science",
            {"CS1201", "CS2303", "CS2306"},
            {"CS2303"},
        )
    )


seed_courses_and_program()


def offering_to_dto(offering):
    return {
        "offering_id": offering.offering_id,
        "course_code": offering.course_code,
        "semester": offering.semester,
        "faculty_id": offering.faculty_id,
        "capacity": offering.capacity,
        "available_seats": offering.available_seats,
        "slots": [slot.__dict__ for slot in offering.slots],
    }


def course_to_dto(course):
    return {
        "code": course.code,
        "name": course.name,
        "description": course.description,
        "department": course.department,
        "prerequisites": sorted(course.prerequisites),
    }


def enrollment_to_dto(enrollment):
    return {
        "enrollment_id": enrollment.enrollment_id,
        "student_id": enrollment.student_id,
        "offering_id": enrollment.offering_id,
        "status": enrollment.status.value,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "enrollment"}


@app.get("/courses")
def browse_courses(
    department: str | None = None,
    keyword: str | None = None,
    instructor: str | None = None,
):
    matching_courses = []

    for course in course_repository.all_courses():
        if department and course.department.lower() != department.lower():
            continue
        if keyword and keyword.lower() not in (
            f"{course.code} {course.name} {course.description}".lower()
        ):
            continue

        for offering in course_repository.all_offerings():
            if offering.course_code != course.code:
                continue
            if instructor and offering.faculty_id != instructor:
                continue

            faculty = get_identity_data(f"/users/{offering.faculty_id}")
            matching_courses.append(
                {
                    **course_to_dto(course),
                    "instructor": {
                        "user_id": faculty["user_id"],
                        "name": faculty["name"],
                    },
                    "offering": offering_to_dto(offering),
                }
            )

    return matching_courses


@app.post("/courses", status_code=201)
def create_course(body: CourseIn):
    if course_repository.get_course(body.code):
        raise HTTPException(409, "Course already exists")

    course = Course(
        body.code,
        body.name,
        body.description,
        body.department,
        set(body.prerequisites),
    )
    course_repository.save_course(course)
    return course_to_dto(course)


@app.put("/courses/{code}")
def update_course(code: str, body: CourseIn):
    course = course_repository.get_course(code)
    if not course:
        raise HTTPException(404, "Course not found")

    course.name = body.name
    course.description = body.description
    course.department = body.department
    course.prerequisites = set(body.prerequisites)
    course_repository.save_course(course)
    return course_to_dto(course)


@app.delete("/courses/{code}")
def delete_course(code: str):
    if code not in course_repository.courses:
        raise HTTPException(404, "Course not found")

    del course_repository.courses[code]
    return {"deleted": code}


@app.post("/offerings", status_code=201)
def create_offering(body: OfferingIn):
    if not course_repository.get_course(body.course_code):
        raise HTTPException(400, "Unknown course")

    offering = CourseOffering(
        body.offering_id,
        body.course_code,
        body.semester,
        body.faculty_id,
        body.capacity,
        [TimeSlot(**slot.model_dump()) for slot in body.slots],
    )
    course_repository.save_offering(offering)
    return offering_to_dto(offering)


@app.get("/offerings/{offering_id}")
def get_offering(offering_id: str):
    offering = course_repository.get_offering(offering_id)
    if not offering:
        raise HTTPException(404, "Offering not found")
    return offering_to_dto(offering)


@app.post("/programs", status_code=201)
def create_program(body: ProgramIn):
    unknown_courses = [
        course_code
        for course_code in body.required_courses
        if not course_repository.get_course(course_code)
    ]
    if unknown_courses:
        raise HTTPException(
            400,
            f"Unknown course(s): {', '.join(unknown_courses)}",
        )

    program = DegreeProgram(
        body.program_code,
        body.name,
        set(body.required_courses),
        set(body.critical_courses),
    )
    program_repository.save(program)
    return {
        "program_code": program.program_code,
        "name": program.name,
        "required_courses": sorted(program.required_courses),
        "critical_courses": sorted(program.critical_courses),
    }


@app.post("/enrollments")
def enroll_student(body: EnrollmentIn):
    student_data = get_identity_data(f"/users/{body.student_id}")
    if student_data["role"] != "student":
        raise HTTPException(400, "Student not found")

    offering = course_repository.get_offering(body.offering_id)
    if not offering:
        raise HTTPException(404, "Course offering not found")

    existing_enrollment = enrollment_repository.get(
        body.student_id, body.offering_id
    )
    if existing_enrollment and existing_enrollment.status in {
        EnrollmentStatus.ENROLLED,
        EnrollmentStatus.WAITLISTED,
    }:
        return {
            **enrollment_to_dto(existing_enrollment),
            "validation": {
                "passed": False,
                "failure": ValidationFailure.ALREADY_ENROLLED.value,
                "message": (
                    "Student already has an active enrolment/waitlist entry."
                ),
            },
        }

    student = Student(
        user_id=body.student_id,
        name=student_data["name"],
        email=student_data["email"],
        role=UserRole.STUDENT,
        active=student_data.get("active", True),
        completed_courses=student_data.get("completed_courses", {}),
    )
    validation = enrollment_validator.validate(student, offering)

    if (
        not validation.passed
        and validation.failure != ValidationFailure.CAPACITY
    ):
        dropped_enrollment = Enrollment(
            body.student_id,
            body.offering_id,
            EnrollmentStatus.DROPPED,
        )
        enrollment_repository.save(dropped_enrollment)
        return {
            **enrollment_to_dto(dropped_enrollment),
            "validation": validation.__dict__,
        }

    enrollment = Enrollment(
        body.student_id,
        body.offering_id,
        (
            EnrollmentStatus.WAITLISTED
            if not validation.passed
            else EnrollmentStatus.ENROLLED
        ),
    )

    try:
        with unit_of_work:
            if enrollment.status == EnrollmentStatus.WAITLISTED:
                add_to_waitlist_if_needed(body.student_id, offering)
            else:
                enroll_student_in_offering(body, offering)

            course_repository.save_offering(offering)
            enrollment_repository.save(enrollment)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    if enrollment.status == EnrollmentStatus.ENROLLED:
        event_publisher.publish(
            DomainEvent(
                "enrollment_confirmed",
                {
                    "student_id": body.student_id,
                    "offering_id": body.offering_id,
                },
            )
        )

    return {
        **enrollment_to_dto(enrollment),
        "validation": validation.__dict__,
    }


def add_to_waitlist_if_needed(student_id: str, offering: CourseOffering):
    if student_id not in offering.waitlisted_student_ids:
        offering.waitlisted_student_ids.append(student_id)


def enroll_student_in_offering(body: EnrollmentIn, offering: CourseOffering):
    offering.enrolled_student_ids.add(body.student_id)
    schedule_repository.add(body.student_id, body.offering_id)
    if body.student_id in offering.waitlisted_student_ids:
        offering.waitlisted_student_ids.remove(body.student_id)


@app.delete("/enrollments/{student_id}/{offering_id}")
def drop_enrollment(student_id: str, offering_id: str):
    offering = course_repository.get_offering(offering_id)
    enrollment = enrollment_repository.get(student_id, offering_id)
    if (
        not offering
        or not enrollment
        or enrollment.status != EnrollmentStatus.ENROLLED
    ):
        raise HTTPException(404, "Active enrolment not found")

    was_full = offering.is_full
    with unit_of_work:
        offering.enrolled_student_ids.remove(student_id)
        course_repository.save_offering(offering)
        schedule_repository.remove(student_id, offering_id)
        enrollment.status = EnrollmentStatus.DROPPED
        enrollment_repository.save(enrollment)

    if was_full:
        event_publisher.publish(
            DomainEvent(
                "seat_available",
                {
                    "offering_id": offering_id,
                    "waitlisted_student_ids": list(
                        offering.waitlisted_student_ids
                    ),
                },
            )
        )

    return enrollment_to_dto(enrollment)


@app.get("/students/{student_id}/schedule")
def get_schedule(student_id: str):
    schedule = []
    for offering_id in sorted(schedule_repository.get(student_id)):
        offering = course_repository.get_offering(offering_id)
        if offering:
            schedule.append(offering_to_dto(offering))
    return schedule


@app.get("/students/{student_id}/progress/{program_code}")
def get_progress(student_id: str, program_code: str):
    student = get_identity_data(f"/users/{student_id}")
    program = program_repository.get(program_code)
    if not program or student["role"] != "student":
        raise HTTPException(404, "Student or program not found")

    completed_courses = student.get("completed_courses", {})
    required_courses = sorted(program.required_courses)
    completed_required_courses = {
        course_code: completed_courses[course_code]
        for course_code in required_courses
        if course_code in completed_courses
    }
    remaining_courses = [
        course_code
        for course_code in required_courses
        if course_code not in completed_courses
    ]
    return {
        "student_id": student_id,
        "program": program.name,
        "completed": completed_required_courses,
        "remaining": remaining_courses,
    }


@app.get("/internal/roster/{offering_id}")
def get_roster(offering_id: str):
    offering = course_repository.get_offering(offering_id)
    if not offering:
        raise HTTPException(404, "Offering not found")

    students = [
        get_identity_data(f"/users/{student_id}")
        for student_id in sorted(offering.enrolled_student_ids)
    ]
    return {"offering_id": offering_id, "students": students}


@app.post("/internal/override", status_code=200)
def override_enrollment(body: EnrollmentIn):
    student = get_identity_data(f"/users/{body.student_id}")
    offering = course_repository.get_offering(body.offering_id)
    if student["role"] != "student" or not offering:
        raise HTTPException(404, "Student or offering not found")

    with unit_of_work:
        offering.enrolled_student_ids.add(body.student_id)
        if body.student_id in offering.waitlisted_student_ids:
            offering.waitlisted_student_ids.remove(body.student_id)
        schedule_repository.add(body.student_id, body.offering_id)
        course_repository.save_offering(offering)

        enrollment = Enrollment(
            body.student_id,
            body.offering_id,
            EnrollmentStatus.ENROLLED,
        )
        enrollment_repository.save(enrollment)

    return enrollment_to_dto(enrollment)


@app.post("/internal/course-changes/execute")
def execute_course_change(body: ChangeExecute):
    command = build_course_change_command(body.action, body.payload)
    command.execute(course_repository)
    return {"executed": True}
