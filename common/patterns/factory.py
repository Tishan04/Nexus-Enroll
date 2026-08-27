from abc import ABC, abstractmethod

from common.domain.models import Administrator, Faculty, Student, User, UserRole


class UserCreator(ABC):
    @abstractmethod
    def create(
        self, user_id: str, name: str, email: str, **kwargs
    ) -> User:
        ...


class StudentCreator(UserCreator):
    def create(self, user_id: str, name: str, email: str, **kwargs) -> User:
        return Student(user_id, name, email, UserRole.STUDENT)


class FacultyCreator(UserCreator):
    def create(self, user_id: str, name: str, email: str, **kwargs) -> User:
        department = kwargs.get("department", "")
        return Faculty(user_id, name, email, UserRole.FACULTY, department)


class AdministratorCreator(UserCreator):
    def create(self, user_id: str, name: str, email: str, **kwargs) -> User:
        return Administrator(user_id, name, email, UserRole.ADMINISTRATOR)


class UserFactory:
    """Creates user types without coupling identity logic to API routing."""

    def __init__(self):
        self._creators = {
            UserRole.STUDENT: StudentCreator(),
            UserRole.FACULTY: FacultyCreator(),
            UserRole.ADMINISTRATOR: AdministratorCreator(),
        }

    def create(
        self,
        role: UserRole,
        user_id: str,
        name: str,
        email: str,
        **kwargs,
    ) -> User:
        return self._creators[role].create(user_id, name, email, **kwargs)
