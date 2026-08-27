from copy import deepcopy


class UserRepository:
    def __init__(self):
        self.users = {}

    def save(self, user):
        self.users[user.user_id] = user

    def get(self, user_id):
        return self.users.get(user_id)

    def all(self):
        return list(self.users.values())


class CourseRepository:
    def __init__(self):
        self.courses = {}
        self.offerings = {}

    def save_course(self, course):
        self.courses[course.code] = course

    def get_course(self, course_code):
        return self.courses.get(course_code)

    def all_courses(self):
        return list(self.courses.values())

    def save_offering(self, offering):
        self.offerings[offering.offering_id] = offering

    def get_offering(self, offering_id):
        return self.offerings.get(offering_id)

    def all_offerings(self):
        return list(self.offerings.values())


class ProgramRepository:
    def __init__(self):
        self.programs = {}

    def save(self, program):
        self.programs[program.program_code] = program

    def get(self, program_code):
        return self.programs.get(program_code)

    def all(self):
        return list(self.programs.values())


class EnrollmentRepository:
    def __init__(self):
        self.enrollments = {}

    def save(self, enrollment):
        key = (enrollment.student_id, enrollment.offering_id)
        self.enrollments[key] = enrollment

    def get(self, student_id, offering_id):
        return self.enrollments.get((student_id, offering_id))

    def for_student(self, student_id):
        return [
            enrollment
            for (stored_student_id, _), enrollment in self.enrollments.items()
            if stored_student_id == student_id
        ]

    def all(self):
        return list(self.enrollments.values())


class ScheduleRepository:
    def __init__(self):
        self.schedules = {}

    def add(self, student_id, offering_id):
        self.schedules.setdefault(student_id, set()).add(offering_id)

    def remove(self, student_id, offering_id):
        self.schedules.setdefault(student_id, set()).discard(offering_id)

    def get(self, student_id):
        return set(self.schedules.get(student_id, set()))


class GradeRepository:
    def __init__(self):
        self.grades = {}

    def save(self, grade_submission):
        self.grades[grade_submission.submission_id] = grade_submission

    def get(self, submission_id):
        return self.grades.get(submission_id)

    def all(self):
        return list(self.grades.values())


class ChangeRepository:
    def __init__(self):
        self.change_requests = {}

    def save(self, change_request):
        self.change_requests[change_request.request_id] = change_request

    def get(self, request_id):
        return self.change_requests.get(request_id)

    def all(self):
        return list(self.change_requests.values())


class UnitOfWork:
    """Provides a simple rollback boundary for the prototype's in-memory writes."""

    def __init__(self, repositories):
        self.repositories = repositories
        self.snapshots = None

    def __enter__(self):
        self.snapshots = [
            deepcopy(repository.__dict__) for repository in self.repositories
        ]
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type:
            for repository, snapshot in zip(self.repositories, self.snapshots):
                repository.__dict__.clear()
                repository.__dict__.update(snapshot)
        return False
