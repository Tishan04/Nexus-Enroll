from common.domain.models import(Course, CourseOffering, GradeStatus, Student, UserRole, GradeSubmission)
from common.patterns.command import ChangeDescriptionCommand
from common.patterns.factory import UserFactory
from common.patterns.state import get_grade_state
from common.patterns.validation import build_enrollment_validation_chain
from common.repositories.memory import CourseRepository, ScheduleRepository

def test_factory_creates_required_roles():
    user_factory = UserFactory()

    student = user_factory.create(UserRole.STUDENT, "S1", "N", "n@n")
    faculty = user_factory.create(UserRole.FACULTY, "F1", "F", "f@n", department="CS")
    administrator = user_factory.create(UserRole.ADMINISTRATOR, "A1", "A", "a@n")

    assert student.role == UserRole.STUDENT
    assert faculty.role == UserRole.FACULTY
    assert administrator.role == UserRole.ADMINISTRATOR

def test_chain_rejects_missing_prerequisite():
    course_repository = CourseRepository()
    schedule_repository = ScheduleRepository()
    course_repository.save_course(Course("CS1", "Intro", "", "CS"))
    course_repository.save_course(Course("CS2", "Adv", "", "CS", {"CS1"}))
    offering = CourseOffering("O1", "CS2", "S1", "F1", 10)
    student = UserFactory().create(UserRole.STUDENT, "S1", "N", "n@n")

    validation_chain = build_enrollment_validation_chain(course_repository, schedule_repository)
    result = validation_chain.validate(student, offering)

    assert not result.passed
    assert result.failure.value == "prerequisite"

def test_command_changes_course_description():
    course_repository = CourseRepository()
    course_repository.save_course(Course("CS1", "Intro", "old", "CS"))

    ChangeDescriptionCommand("CS1", "new").execute(course_repository)

    assert course_repository.get_course("CS1").description == "new"

def test_state_transitions_grade():
    grade_submission = GradeSubmission("F1", "S1", "O1", "A")

    get_grade_state(grade_submission).submit(grade_submission)
    assert grade_submission.status == GradeStatus.PENDING

    get_grade_state(grade_submission).approve(grade_submission)
    assert grade_submission.status == GradeStatus.SUBMITTED
