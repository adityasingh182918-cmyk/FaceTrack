"""Minimal desktop HTTP client for the FACETRACK backend API."""

from __future__ import annotations

import json
from pathlib import Path
from urllib import error, parse, request
from uuid import uuid4

from utils.config import BACKEND_API_BASE_URL, BACKEND_API_ENABLED, BACKEND_API_TIMEOUT_SECONDS


class BackendApiError(RuntimeError):
    """Raised when the backend API is unavailable or returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendApiClient:
    """Small JSON HTTP client used by the desktop app."""

    _session_token: str | None = None

    def __init__(self, base_url: str = BACKEND_API_BASE_URL, timeout: int = BACKEND_API_TIMEOUT_SECONDS) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.enabled = BACKEND_API_ENABLED

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict | list:
        if not self.enabled:
            raise BackendApiError("Backend API disabled for desktop runtime.")

        url = f"{self.base_url}{path}"
        body = None
        headers = {"Accept": "application/json"}
        if type(self)._session_token and path != "/auth/login":
            headers["Authorization"] = f"Bearer {type(self)._session_token}"
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                try:
                    return json.loads(raw.decode("utf-8")) if raw else {}
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise BackendApiError("Backend returned an invalid JSON response.", status_code=response.status) from exc
        except error.HTTPError as exc:
            if exc.code == 401:
                type(self)._session_token = None
            detail = exc.reason
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                detail = payload.get("detail", detail)
            except (ValueError, UnicodeDecodeError, AttributeError):
                detail = exc.reason
            raise BackendApiError(str(detail), status_code=exc.code) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise BackendApiError(str(exc)) from exc

    def health(self) -> dict:
        return self._request("GET", "/health")

    def login(self, username: str, password: str, role: str) -> dict:
        type(self)._session_token = None
        response = self._request("POST", "/auth/login", {"username": username, "password": password, "role": role})
        type(self)._session_token = response["access_token"]
        return response

    def clear_session(self) -> None:
        type(self)._session_token = None

    def list_faculty(self, include_admin: bool = True) -> list[dict]:
        query = parse.urlencode({"include_admin": str(include_admin).lower()})
        return self._request("GET", f"/faculty?{query}")

    def list_students(self) -> list[dict]:
        return self._request("GET", "/students")

    def list_student_encodings(self, section: str | None = None) -> list[dict]:
        query = f"?{parse.urlencode({'section': section})}" if section else ""
        return self._request("GET", f"/students/encodings{query}")

    def get_student(self, roll_no: str) -> dict:
        return self._request("GET", f"/students/{parse.quote(roll_no)}")

    def get_student_attendance_summary(self, roll_no: str) -> dict:
        return self._request("GET", f"/students/{parse.quote(roll_no)}/attendance-summary")

    def get_timetable(self, faculty: str | None = None, section: str | None = None, day: str | None = None) -> list[dict]:
        params = {}
        if faculty:
            params["faculty"] = faculty
        if section:
            params["section"] = section
        if day:
            params["day"] = day
        query = f"?{parse.urlencode(params)}" if params else ""
        return self._request("GET", f"/timetable{query}")

    def get_today_classes(self, faculty: str | None = None) -> list[dict]:
        query = f"?{parse.urlencode({'faculty': faculty})}" if faculty else ""
        return self._request("GET", f"/timetable/today{query}")

    def get_attendance_records(self, roll_no: str | None = None, subject: str | None = None) -> list[dict]:
        params = {}
        if roll_no:
            params["roll_no"] = roll_no
        if subject:
            params["subject"] = subject
        query = f"?{parse.urlencode(params)}" if params else ""
        return self._request("GET", f"/attendance{query}")

    def get_late_flag_report(self) -> list[dict]:
        return self._request("GET", "/reports/late-flags")

    def create_faculty(self, name: str, username: str, password: str, role: str = "faculty") -> dict:
        return self._request(
            "POST",
            "/faculty",
            {"name": name, "username": username, "password": password, "role": role},
        )

    def delete_faculty(self, username: str) -> dict:
        return self._request("DELETE", f"/faculty/{parse.quote(username)}")

    def create_student(self, payload: dict, face_samples: list[Path] | None = None) -> dict:
        if not face_samples:
            return self._request("POST", "/students", payload)

        boundary = f"----FaceTrack{uuid4().hex}"
        body = bytearray()

        for field_name, value in payload.items():
            if field_name == "face_image_dir":
                continue
            body.extend(f"--{boundary}\r\n".encode("ascii"))
            body.extend(
                f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n{value}\r\n'.encode("utf-8")
            )

        for index, file_path in enumerate(face_samples, start=1):
            body.extend(f"--{boundary}\r\n".encode("ascii"))
            body.extend(
                f'Content-Disposition: form-data; name="files"; filename="sample_{index:02d}.jpg"\r\n'.encode(
                    "ascii"
                )
            )
            body.extend(b"Content-Type: image/jpeg\r\n\r\n")
            body.extend(file_path.read_bytes())
            body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("ascii"))

        return self._request_multipart("/students/register-with-faces", boundary, bytes(body))

    def _request_multipart(self, path: str, boundary: str, body: bytes) -> dict:
        if not self.enabled:
            raise BackendApiError("Backend API disabled for desktop runtime.")

        headers = {
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        if type(self)._session_token:
            headers["Authorization"] = f"Bearer {type(self)._session_token}"
        req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                try:
                    return json.loads(response.read().decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise BackendApiError("Backend returned an invalid JSON response.", status_code=response.status) from exc
        except error.HTTPError as exc:
            if exc.code == 401:
                type(self)._session_token = None
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", exc.reason)
            except (ValueError, AttributeError):
                detail = exc.reason
            raise BackendApiError(str(detail), status_code=exc.code) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise BackendApiError(str(exc)) from exc

    def update_student(self, roll_no: str, payload: dict) -> dict:
        return self._request("PUT", f"/students/{parse.quote(roll_no)}", payload)

    def delete_student(self, roll_no: str) -> dict:
        return self._request("DELETE", f"/students/{parse.quote(roll_no)}")

    def create_timetable_entry(self, payload: dict) -> dict:
        return self._request("POST", "/timetable", payload)

    def update_timetable_entry(self, entry_id: int, payload: dict) -> dict:
        return self._request("PUT", f"/timetable/{entry_id}", payload)

    def delete_timetable_entry(self, entry_id: int) -> dict:
        return self._request("DELETE", f"/timetable/{entry_id}")

    def seed_attendance_session(self, timetable_id: int) -> dict:
        return self._request("POST", "/attendance/session/seed", {"timetable_id": timetable_id})

    def mark_attendance(self, timetable_id: int, roll_no: str) -> dict:
        return self._request("POST", "/attendance/mark", {"timetable_id": timetable_id, "roll_no": roll_no})
