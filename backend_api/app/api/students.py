"""Student endpoints for desktop/web clients."""

from __future__ import annotations

from io import BytesIO
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from backend_api.app.dependencies import get_student_service
from backend_api.app.security import AuthenticatedUser, get_current_user, require_roles
from backend_api.app.schemas import (
    StudentAttendanceSummaryResponse,
    StudentCreateRequest,
    StudentEncodingOut,
    StudentMutationResponse,
    StudentOut,
    StudentUpdateRequest,
)
from services.student_service import StudentService
from services.timetable_service import TimetableService
from utils.config import FACE_SAMPLE_MAX, FACE_SAMPLE_TARGET

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=list[StudentOut])
def list_students(
    student_service: StudentService = Depends(get_student_service),
    current_user: AuthenticatedUser = Depends(require_roles("admin", "faculty")),
) -> list[StudentOut]:
    students = student_service.list_students()
    if current_user.role == "faculty":
        sections = {entry.section for entry in TimetableService().list_entries(faculty=current_user.username)}
        students = [student for student in students if student.section in sections]
    return [
        StudentOut(
            id=student.id,
            roll_no=student.roll_no,
            name=student.name,
            department=student.department,
            year=student.year,
            section=student.section,
            red_flags=student.red_flags,
            created_at=student.created_at,
        )
        for student in students
    ]


@router.get("/encodings", response_model=list[StudentEncodingOut])
def list_student_encodings(
    section: str | None = None,
    student_service: StudentService = Depends(get_student_service),
    current_user: AuthenticatedUser = Depends(require_roles("admin", "faculty")),
) -> list[StudentEncodingOut]:
    rows = student_service.get_all_student_encodings()
    if current_user.role == "faculty":
        sections = {entry.section for entry in TimetableService().list_entries(faculty=current_user.username)}
        rows = [row for row in rows if row["section"] in sections]
    if section:
        rows = [row for row in rows if row["section"] == section]
    return [
        StudentEncodingOut(
            roll_no=row["roll_no"],
            name=row["name"],
            section=row["section"],
            department=row["department"],
            year=row["year"],
            red_flags=row["red_flags"],
            encodings=[encoding.astype(float).tolist() for encoding in row["encodings"]],
        )
        for row in rows
    ]


@router.get("/{roll_no}", response_model=StudentOut)
def get_student(
    roll_no: str,
    student_service: StudentService = Depends(get_student_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> StudentOut:
    student = student_service.get_student_by_roll(roll_no.upper())
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    if current_user.role == "student" and current_user.roll_no != student.roll_no:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only view their own profile.")
    if current_user.role == "faculty":
        sections = {entry.section for entry in TimetableService().list_entries(faculty=current_user.username)}
        if student.section not in sections:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is outside your assigned classes.")
    return StudentOut(
        id=student.id,
        roll_no=student.roll_no,
        name=student.name,
        department=student.department,
        year=student.year,
        section=student.section,
        red_flags=student.red_flags,
        created_at=student.created_at,
    )


@router.get("/{roll_no}/attendance-summary", response_model=StudentAttendanceSummaryResponse)
def get_student_attendance_summary(
    roll_no: str,
    student_service: StudentService = Depends(get_student_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> StudentAttendanceSummaryResponse:
    student = student_service.get_student_by_roll(roll_no.upper())
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    if current_user.role == "student" and current_user.roll_no != student.roll_no:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only view their own attendance.")
    if current_user.role == "faculty":
        sections = {entry.section for entry in TimetableService().list_entries(faculty=current_user.username)}
        if student.section not in sections:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is outside your assigned classes.")

    overall, subject_summaries = student_service.get_attendance_summary(student.roll_no)
    return StudentAttendanceSummaryResponse(
        roll_no=student.roll_no,
        overall_percentage=overall,
        subject_summaries=[
            {
                "subject": item.subject,
                "present": item.present,
                "total": item.total,
                "percentage": item.percentage,
                "late_flags": item.late_flags,
            }
            for item in subject_summaries
        ],
    )


@router.post("", response_model=StudentMutationResponse)
def create_student(
    payload: StudentCreateRequest,
    student_service: StudentService = Depends(get_student_service),
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> StudentMutationResponse:
    success, message = student_service.register_student_payload(
        {
            "roll_no": payload.roll_no.upper(),
            "name": payload.name,
            "department": payload.department,
            "year": payload.year,
            "section": payload.section.upper(),
            "password": payload.password,
            "face_image_dir": "",
        },
        payload.serialized_encoding,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return StudentMutationResponse(success=success, message=message)


@router.post("/register-with-faces", response_model=StudentMutationResponse)
async def register_student_with_faces(
    roll_no: str = Form(min_length=1),
    name: str = Form(min_length=1),
    department: str = Form(min_length=1),
    year: int = Form(ge=1, le=6),
    section: str = Form(min_length=1),
    password: str = Form(min_length=8, max_length=128),
    serialized_encoding: str = Form(min_length=1, max_length=1_000_000),
    files: list[UploadFile] = File(...),
    student_service: StudentService = Depends(get_student_service),
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> StudentMutationResponse:
    if not FACE_SAMPLE_TARGET <= len(files) <= FACE_SAMPLE_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload between {FACE_SAMPLE_TARGET} and {FACE_SAMPLE_MAX} face samples.",
        )

    validated_files: list[tuple[str, bytes]] = []
    total_size = 0
    try:
        for upload in files:
            content = await upload.read(2 * 1024 * 1024 + 1)
            total_size += len(content)
            if not content or len(content) > 2 * 1024 * 1024 or total_size > 30 * 1024 * 1024:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Face sample upload is too large.")
            try:
                with Image.open(BytesIO(content)) as image:
                    image_format = image.format
                    if image_format not in {"JPEG", "PNG"} or image.width * image.height > 20_000_000:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Face samples must be JPEG or PNG images.")
                    image.verify()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A face sample is not a valid image.") from exc
            validated_files.append((".jpg" if image_format == "JPEG" else ".png", content))
    finally:
        for upload in files:
            await upload.close()

    if student_service.get_student_by_roll(roll_no.strip().upper()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Roll number already exists.")

    try:
        stored_dir = student_service.save_face_samples(
            files=validated_files,
        )
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to store face samples.") from exc

    success = False
    try:
        success, message = student_service.register_student_payload(
            {
                "roll_no": roll_no.strip().upper(),
                "name": name.strip(),
                "department": department.strip(),
                "year": year,
                "section": section.strip().upper(),
                "password": password,
                "face_image_dir": str(stored_dir),
            },
            serialized_encoding,
        )
    finally:
        if not success:
            shutil.rmtree(stored_dir, ignore_errors=True)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return StudentMutationResponse(success=success, message=message)


@router.put("/{roll_no}", response_model=StudentMutationResponse)
def update_student(
    roll_no: str,
    payload: StudentUpdateRequest,
    student_service: StudentService = Depends(get_student_service),
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> StudentMutationResponse:
    success, message = student_service.update_student_profile(
        roll_no.upper(),
        {
            "roll_no": payload.roll_no.upper(),
            "name": payload.name,
            "department": payload.department,
            "year": payload.year,
            "section": payload.section.upper(),
            "password": payload.password,
        },
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return StudentMutationResponse(success=success, message=message)


@router.delete("/{roll_no}", response_model=StudentMutationResponse)
def delete_student(
    roll_no: str,
    student_service: StudentService = Depends(get_student_service),
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> StudentMutationResponse:
    success, message = student_service.delete_student(roll_no.upper())
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    return StudentMutationResponse(success=success, message=message)
