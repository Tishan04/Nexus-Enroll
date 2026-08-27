from abc import ABC, abstractmethod
from dataclasses import dataclass

from common.domain.models import CourseOffering, Student, ValidationFailure


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    failure: ValidationFailure | None = None
    message: str = ""


class EnrollmentValidator(ABC):
    def __init__(self):
        self._next_validator = None

    def set_next(self, validator):
        self._next_validator = validator
        return validator

    def validate(
        self, student: Student, offering: CourseOffering
    ) -> ValidationResult:
        result = self.check(student, offering)
        if not result.passed:
            return result

        if self._next_validator:
            return self._next_validator.validate(student, offering)
        return result

    @abstractmethod
    def check(self, student: Student, offering: CourseOffering) -> ValidationResult:
        ...


class PrerequisiteValidator(EnrollmentValidator):
    def __init__(self, courses):
        super().__init__()
        self.courses = courses

    def check(self, student: Student, offering: CourseOffering) -> ValidationResult:
        course = self.courses.get_course(offering.course_code)
        missing_prerequisites = sorted(
            course.prerequisites - set(student.completed_courses)
        )
        if missing_prerequisites:
            return ValidationResult(
                False,
                ValidationFailure.PREREQUISITE,
                f"Missing prerequisite(s): {', '.join(missing_prerequisites)}",
            )
        return ValidationResult(True)


class TimeConflictValidator(EnrollmentValidator):
    def __init__(self, courses, schedules):
        super().__init__()
        self.courses = courses
        self.schedules = schedules

    def check(self, student: Student, offering: CourseOffering) -> ValidationResult:
        for existing_offering_id in self.schedules.get(student.user_id):
            existing_offering = self.courses.get_offering(existing_offering_id)
            if existing_offering and any(
                existing_slot.conflicts_with(requested_slot)
                for existing_slot in existing_offering.slots
                for requested_slot in offering.slots
            ):
                return ValidationResult(
                    False,
                    ValidationFailure.TIME_CONFLICT,
                    f"Time conflict with {existing_offering.offering_id}.",
                )
        return ValidationResult(True)


class CapacityValidator(EnrollmentValidator):
    def check(self, student: Student, offering: CourseOffering) -> ValidationResult:
        if offering.is_full:
            return ValidationResult(
                False,
                ValidationFailure.CAPACITY,
                "Course offering is full.",
            )
        return ValidationResult(True)


def build_enrollment_validation_chain(courses, schedules):
    prerequisite_validator = PrerequisiteValidator(courses)
    time_conflict_validator = TimeConflictValidator(courses, schedules)
    capacity_validator = CapacityValidator()

    prerequisite_validator.set_next(time_conflict_validator).set_next(
        capacity_validator
    )
    return prerequisite_validator
