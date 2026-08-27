from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common.domain.models import Administrator, Faculty, Student, UserRole
from common.patterns.factory import UserFactory
from common.repositories.memory import UserRepository


app = FastAPI(title="NexusEnroll Identity Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_repository = UserRepository()
user_factory = UserFactory()


class UserCreate(BaseModel):
    user_id: str
    name: str
    email: str
    role: UserRole
    department: str = ""


class UserPatch(BaseModel):
    active: bool | None = None
    name: str | None = None
    email: str | None = None


def seed_users():
    seed_data = [
        ("A001", "Ava Perera", "ava@nexus.edu", UserRole.ADMINISTRATOR, ""),
        (
            "F001",
            "Dr. Senanayake",
            "senanayake@nexus.edu",
            UserRole.FACULTY,
            "Computer Science",
        ),
        ("S001", "Nimal Silva", "nimal@nexus.edu", UserRole.STUDENT, ""),
        ("S002", "Maya Fernando", "maya@nexus.edu", UserRole.STUDENT, ""),
        ("S003", "Ishan Jay", "ishan@nexus.edu", UserRole.STUDENT, ""),
    ]

    for user_id, name, email, role, department in seed_data:
        user = user_factory.create(
            role,
            user_id,
            name,
            email,
            department=department,
        )
        if isinstance(user, Student) and user_id in {"S001", "S002"}:
            user.completed_courses["CS1201"] = (
                "A" if user_id == "S001" else "B+"
            )
        user_repository.save(user)


seed_users()


def to_user_dto(user):
    result = {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "active": user.active,
    }
    if isinstance(user, Faculty):
        result["department"] = user.department
    if isinstance(user, Student):
        result["completed_courses"] = user.completed_courses
    return result


@app.get("/health")
def health():
    return {"status": "ok", "service": "identity"}


@app.get("/users")
def list_users(role: UserRole | None = None):
    return [
        to_user_dto(user)
        for user in user_repository.all()
        if role is None or user.role == role
    ]


@app.get("/users/{user_id}")
def get_user(user_id: str):
    user = user_repository.get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return to_user_dto(user)


@app.post("/users", status_code=201)
def create_user(body: UserCreate):
    if user_repository.get(body.user_id):
        raise HTTPException(409, "User already exists")

    try:
        user = user_factory.create(
            body.role,
            body.user_id,
            body.name,
            body.email,
            department=body.department,
        )
        user_repository.save(user)
        return to_user_dto(user)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.patch("/users/{user_id}")
def update_user(user_id: str, body: UserPatch):
    user = user_repository.get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    if body.active is not None:
        user.active = body.active
    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        user.email = body.email

    return to_user_dto(user)


@app.get("/students/{student_id}/completed-courses")
def get_completed_courses(student_id: str):
    user = user_repository.get(student_id)
    if not isinstance(user, Student):
        raise HTTPException(404, "Student not found")
    return {
        "student_id": student_id,
        "completed_courses": user.completed_courses,
    }


@app.put("/students/{student_id}/completed-courses/{course_code}")
def add_completed_course(student_id: str, course_code: str, grade: str):
    user = user_repository.get(student_id)
    if not isinstance(user, Student):
        raise HTTPException(404, "Student not found")

    user.completed_courses[course_code] = grade
    return {
        "student_id": student_id,
        "course_code": course_code,
        "grade": grade,
    }
