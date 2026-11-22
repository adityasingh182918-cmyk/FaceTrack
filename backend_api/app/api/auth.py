"""Authentication endpoints for admin, faculty, and student portals."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend_api.app.dependencies import get_student_service
from backend_api.app.schemas import AuthUserOut, LoginRequest, LoginResponse
from backend_api.app.security import create_access_token
from database.db import db_manager
from services.student_service import StudentService
from utils.helpers import hash_password, password_needs_rehash, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, student_service: StudentService = Depends(get_student_service)) -> LoginResponse:
    if payload.role in {"admin", "faculty"}:
        with db_manager.connection() as conn:
            row = conn.execute(
                "SELECT id, username, name, role, password FROM Faculty WHERE username = ?",
                (payload.username.strip(),),
            ).fetchone()
            if not row or not verify_password(payload.password, row["password"]):
                row = None
            elif password_needs_rehash(row["password"]):
                conn.execute(
                    "UPDATE Faculty SET password = ? WHERE username = ?",
                    (hash_password(payload.password), payload.username.strip()),
                )
        if not row or row["role"] != payload.role:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        user = AuthUserOut(
            id=row["id"],
            username=row["username"],
            name=row["name"],
            role=row["role"],
        )
        return LoginResponse(
            access_type=payload.role,
            user=user,
            access_token=create_access_token(user.model_dump()),
        )

    student = student_service.authenticate_student(payload.username.strip().upper(), payload.password)
    if not student:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    user = AuthUserOut(
        id=student.id,
        roll_no=student.roll_no,
        name=student.name,
        role="student",
        department=student.department,
        year=student.year,
        section=student.section,
        red_flags=student.red_flags,
    )
    return LoginResponse(
        access_type="student",
        user=user,
        access_token=create_access_token(user.model_dump()),
    )
