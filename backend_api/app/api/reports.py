"""Reporting endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend_api.app.dependencies import get_attendance_service
from backend_api.app.security import AuthenticatedUser, require_roles
from backend_api.app.schemas import LateFlagReportRow
from services.attendance_service import AttendanceService
from services.timetable_service import TimetableService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/late-flags", response_model=list[LateFlagReportRow])
def late_flag_report(
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: AuthenticatedUser = Depends(require_roles("admin", "faculty")),
) -> list[LateFlagReportRow]:
    rows = attendance_service.get_late_student_report()
    if current_user.role == "faculty":
        sections = {entry.section for entry in TimetableService().list_entries(faculty=current_user.username)}
        rows = [row for row in rows if row["section"] in sections]
    return [LateFlagReportRow(**row) for row in rows]
