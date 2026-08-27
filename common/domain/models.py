from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class UserRole(str, Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    ADMINISTRATOR = "administrator"


class EnrollmentStatus(str, Enum):
    ENROLLED = "enrolled"
    WAITLISTED = "waitlisted"
    DROPPED = "dropped"


class ValidationFailure(str, Enum):
    PREREQUISITE = "prerequisite"
    CAPACITY = "capacity"
    TIME_CONFLICT = "time_conflict"
    NOT_FOUND = "not_found"
    INACTIVE_USER = "inactive_user"
    ALREADY_ENROLLED = "already_enrolled"


class GradeStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    SUBMITTED = "submitted"
    REJECTED = "rejected"


class ChangeRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class User:
    user_id: str
    name: str
    email: str
    role: UserRole
    active: bool = True


@dataclass
class Student(User):
    completed_courses: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.role != UserRole.STUDENT:
            raise ValueError("Student must have STUDENT role")


@dataclass
class Faculty(User):
    department: str = ""

    def __post_init__(self):
        if self.role != UserRole.FACULTY:
            raise ValueError("Faculty must have FACULTY role")


@dataclass
class Administrator(User):
    def __post_init__(self):
        if self.role != UserRole.ADMINISTRATOR:
            raise ValueError("Administrator must have ADMINISTRATOR role")


@dataclass(frozen=True)
class TimeSlot:
    day: str
    start_minute: int
    end_minute: int
    location: str

    def conflicts_with(self, other: "TimeSlot") -> bool:
        if self.day.lower() != other.day.lower():
            return False
        return (
            self.start_minute < other.end_minute
            and other.start_minute < self.end_minute
        )


@dataclass
class Course:
    code: str
    name: str
    description: str
    department: str
    prerequisites: set[str] = field(default_factory=set)


@dataclass
class CourseOffering:
    offering_id: str
    course_code: str
    semester: str
    faculty_id: str
    capacity: int
    slots: list[TimeSlot] = field(default_factory=list)
    enrolled_student_ids: set[str] = field(default_factory=set)
    waitlisted_student_ids: list[str] = field(default_factory=list)

    @property
    def available_seats(self) -> int:
        return max(0, self.capacity - len(self.enrolled_student_ids))

    @property
    def is_full(self) -> bool:
        return self.available_seats == 0


@dataclass
class DegreeProgram:
    program_code: str
    name: str
    required_courses: set[str] = field(default_factory=set)
    critical_courses: set[str] = field(default_factory=set)


@dataclass
class Enrollment:
    student_id: str
    offering_id: str
    status: EnrollmentStatus
    enrollment_id: str = field(
        default_factory=lambda: f"ENR-{uuid4().hex[:8].upper()}"
    )


@dataclass
class GradeSubmission:
    faculty_id: str
    student_id: str
    offering_id: str
    grade: str
    status: GradeStatus = GradeStatus.DRAFT
    rejection_reason: str | None = None
    submission_id: str = field(
        default_factory=lambda: f"GRD-{uuid4().hex[:8].upper()}"
    )


@dataclass
class CourseChangeRequest:
    faculty_id: str
    course_code: str
    action: str
    payload: dict
    description: str
    status: ChangeRequestStatus = ChangeRequestStatus.PENDING
    request_id: str = field(
        default_factory=lambda: f"CCR-{uuid4().hex[:8].upper()}"
    )
