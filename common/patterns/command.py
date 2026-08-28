from abc import ABC, abstractmethod

class CourseChangeCommand(ABC):
    @abstractmethod
    def execute(self, courses):
        ...

class ChangeDescriptionCommand(CourseChangeCommand):
    def __init__(self, course_code, new_description):
        self.course_code = course_code
        self.new_description = new_description

    def execute(self, courses):
        course = courses.get_course(self.course_code)
        if course is None:
            raise ValueError("Course not found.")

        course.description = self.new_description
        courses.save_course(course)

class AddPrerequisiteCommand(CourseChangeCommand):
    def __init__(self, course_code, prerequisite_code):
        self.course_code = course_code
        self.prerequisite_code = prerequisite_code

    def execute(self, courses):
        course = courses.get_course(self.course_code)
        prerequisite_course = courses.get_course(self.prerequisite_code)
        if course is None or prerequisite_course is None:
            raise ValueError("Course or prerequisite course not found.")

        course.prerequisites.add(self.prerequisite_code)
        courses.save_course(course)

class ChangeCapacityCommand(CourseChangeCommand):
    def __init__(self, offering_id, new_capacity):
        self.offering_id = offering_id
        self.new_capacity = new_capacity

    def execute(self, courses):
        offering = courses.get_offering(self.offering_id)
        if offering is None:
            raise ValueError("Course offering not found.")
        if (
            self.new_capacity <= 0
            or self.new_capacity < len(offering.enrolled_student_ids)
        ):
            raise ValueError("Invalid capacity.")

        offering.capacity = self.new_capacity
        courses.save_offering(offering)


def build_course_change_command(action, payload):
    if action == "change_description":
        return ChangeDescriptionCommand(
            payload["course_code"], payload["new_description"]
        )
    if action == "add_prerequisite":
        return AddPrerequisiteCommand(
            payload["course_code"], payload["prerequisite_code"]
        )
    if action == "change_capacity":
        return ChangeCapacityCommand(payload["offering_id"], payload["new_capacity"])
    raise ValueError("Unsupported course-change command.")
