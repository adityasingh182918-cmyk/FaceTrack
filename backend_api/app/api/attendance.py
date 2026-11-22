"""Attendance record endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend_api.app.dependencies import get_attendance_service
from backend_api.app.security import AuthenticatedUser, get_current_user, require_roles
from backend_api.app.schemas import (
    AttendanceMarkRequest,
    AttendanceMutationResponse,
    AttendanceRecordOut,
    AttendanceSeedRequest,
)
from services.attendance_service import AttendanceService
from services.student_service import StudentService
from services.timetable_service import TimetableService

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("", response_model=list[AttendanceRecordOut])
def list_attendance(
    roll_no: str | None = None,
    subject: str | None = None,
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[AttendanceRecordOut]:
    if current_user.role == "student":
        roll_no = current_user.roll_no
    records = attendance_service.get_records(roll_no=roll_no, subject=subject)
    if current_user.role == "faculty":
        assigned = TimetableService().list_entries(faculty=current_user.username)
        allowed_classes = {(entry.subject, entry.section) for entry in assigned}
        student_sections = {student.roll_no: student.section for student in StudentService().list_students()}
        records = [
            record
            for record in records
            if (record.subject, student_sections.get(record.roll_no)) in allowed_classes
        ]
    return [
        AttendanceRecordOut(
            id=record.id,
            roll_no=record.roll_no,
            name=record.name,
            subject=record.subject,
            date=record.date,
            time=record.time,
            status=record.status,
            late_flags=record.late_flags,
        )
        for record in records
    ]


@router.post("/session/seed", response_model=AttendanceMutationResponse)
def seed_attendance_session(
    payload: AttendanceSeedRequest,
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: AuthenticatedUser = Depends(require_roles("admin", "faculty")),
) -> AttendanceMutationResponse:
    timetable_service = TimetableService()
    student_service = StudentService()
    entry = timetable_service.get_entry_by_id(payload.timetable_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable entry not found.")
    if current_user.role == "faculty" and entry.faculty != current_user.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This class is not assigned to you.")

    students = [student for student in student_service.get_all_student_encodings() if student["section"] == entry.section]
    attendance_service.ensure_session_records(entry, students)
    return AttendanceMutationResponse(success=True, message="Attendance session prepared.")


@router.post("/mark", response_model=AttendanceMutationResponse)
def mark_attendance(
    payload: AttendanceMarkRequest,
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: AuthenticatedUser = Depends(require_roles("admin", "faculty")),
) -> AttendanceMutationResponse:
    timetable_service = TimetableService()
    student_service = StudentService()
    entry = timetable_service.get_entry_by_id(payload.timetable_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable entry not found.")
    if current_user.role == "faculty" and entry.faculty != current_user.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This class is not assigned to you.")

    student = student_service.get_student_by_roll(payload.roll_no.upper())
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    if student.section != entry.section:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student is not enrolled in this class section.",
        )

    success, message = attendance_service.mark_attendance(
        {
            "roll_no": student.roll_no,
            "name": student.name,
            "section": student.section,
        },
        entry,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return AttendanceMutationResponse(success=success, message=message)
