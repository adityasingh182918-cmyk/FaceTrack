from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import database.db as database_module
import services.student_service as student_service_module
import utils.config as config_module
from backend_api.app.main import app
from backend_api.app.security import validate_auth_configuration
from services.student_service import StudentService
from utils.helpers import hash_password, password_needs_rehash, serialize_encodings, verify_password


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data_dir = tmp_path / "data"
    faces_dir = data_dir / "faces"
    monkeypatch.setenv("FACETRACK_ENV", "test")
    monkeypatch.setenv("FACETRACK_JWT_SECRET", "test-secret-with-more-than-thirty-two-characters")
    monkeypatch.setenv("FACETRACK_ALLOWED_ORIGINS", "http://testserver")
    monkeypatch.setattr(database_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(database_module, "FACES_DIR", faces_dir)
    monkeypatch.setattr(database_module.db_manager, "db_path", data_dir / "database.db")
    monkeypatch.setattr(config_module, "LOGS_DIR", data_dir / "logs")
    monkeypatch.setattr(student_service_module, "FACES_DIR", faces_dir)

    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, username: str, password: str, role: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password, "role": role},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["token_type"] == "bearer"
    return result["access_token"]


def _jpeg_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (4, 4), color=(30, 80, 120)).save(output, format="JPEG")
    return output.getvalue()


def test_student_registration_rejects_empty_or_malformed_encodings() -> None:
    service = StudentService()
    payload = {
        "roll_no": "S001",
        "name": "Student One",
        "department": "Engineering",
        "year": 1,
        "section": "B1",
        "password": "student-password",
        "face_image_dir": "",
    }

    assert service.register_student_payload(payload, "[]")[0] is False
    assert service.register_student_payload(payload, '{"not":"an encoding list"}')[0] is False


def test_password_hash_supports_new_and_legacy_records() -> None:
    password = "correct horse battery staple"
    encoded = hash_password(password)

    assert encoded != hash_password(password)
    assert verify_password(password, encoded)
    assert not verify_password("wrong", encoded)
    assert password_needs_rehash(encoded) is False

    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    assert verify_password(password, legacy)
    assert password_needs_rehash(legacy)


def test_production_auth_requires_strong_admin_secret_and_https_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACETRACK_ENV", "production")
    monkeypatch.setenv("FACETRACK_JWT_SECRET", "test-secret-with-more-than-thirty-two-characters")
    monkeypatch.setenv("FACETRACK_ADMIN_PASSWORD", "long-enough-admin-secret")
    monkeypatch.setenv("FACETRACK_ALLOWED_ORIGINS", "http://example.com")

    with pytest.raises(RuntimeError, match="FACETRACK_ALLOWED_ORIGINS"):
        validate_auth_configuration()

    monkeypatch.setenv("FACETRACK_ALLOWED_ORIGINS", "https://example.com")
    validate_auth_configuration()


def test_api_authenticates_roles_and_limits_student_data(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/students").status_code == 401

    admin_token = _login(client, "admin", "admin123", "admin")
    assert client.get("/api/students", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
    assert client.get("/api/students", headers={"Authorization": "Bearer invalid"}).status_code == 401

    created = StudentService().register_student_payload(
        {
            "roll_no": "S001",
            "name": "Student One",
            "department": "Engineering",
            "year": 1,
            "section": "B1",
            "password": "student-password",
            "face_image_dir": "",
        },
        serialize_encodings([np.zeros(128)]),
    )
    assert created[0]
    assert StudentService().register_student_payload(
        {
            "roll_no": "S002",
            "name": "Student Two",
            "department": "Engineering",
            "year": 2,
            "section": "B1",
            "password": "student-password",
            "face_image_dir": "",
        },
        serialize_encodings([np.zeros(128)]),
    )[0]
    student_token = _login(client, "S001", "student-password", "student")
    student_headers = {"Authorization": f"Bearer {student_token}"}
    assert client.get("/api/students/S001", headers=student_headers).status_code == 200
    assert client.get("/api/students/S002", headers=student_headers).status_code == 403
    assert client.get("/api/faculty", headers=student_headers).status_code == 403


def test_faculty_cannot_mark_attendance_for_another_section(client: TestClient) -> None:
    admin_token = _login(client, "admin", "admin123", "admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    for roll_no, section in (("S001", "B1"), ("S002", "B2")):
        assert StudentService().register_student_payload(
            {
                "roll_no": roll_no,
                "name": f"Student {roll_no}",
                "department": "Engineering",
                "year": 1,
                "section": section,
                "password": "student-password",
                "face_image_dir": "",
            },
            serialize_encodings([np.zeros(128)]),
        )[0]
    assert client.post(
        "/api/faculty",
        headers=admin_headers,
        json={"name": "Faculty One", "username": "faculty1", "password": "faculty-password", "role": "faculty"},
    ).status_code == 200
    timetable_response = client.post(
        "/api/timetable",
        headers=admin_headers,
        json={
            "subject": "Mathematics",
            "faculty": "faculty1",
            "day": "Monday",
            "start_time": "09:00",
            "end_time": "10:00",
            "section": "B1",
        },
    )
    assert timetable_response.status_code == 200, timetable_response.text
    timetable_id = client.get(
        "/api/timetable",
        headers=admin_headers,
    ).json()[0]["id"]

    faculty_token = _login(client, "faculty1", "faculty-password", "faculty")
    response = client.post(
        "/api/attendance/mark",
        headers={"Authorization": f"Bearer {faculty_token}"},
        json={"timetable_id": timetable_id, "roll_no": "S002"},
    )
    assert response.status_code == 403


def test_admin_registration_persists_uploaded_face_samples(client: TestClient, tmp_path: Path) -> None:
    token = _login(client, "admin", "admin123", "admin")
    samples = [("files", (f"sample_{index:02}.jpg", _jpeg_bytes(), "image/jpeg")) for index in range(15)]
    response = client.post(
        "/api/students/register-with-faces",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "roll_no": "S002",
            "name": "Student Two",
            "department": "Engineering",
            "year": "2",
            "section": "B2",
            "password": "student-password",
            "serialized_encoding": serialize_encodings([np.zeros(128)]),
        },
        files=samples,
    )
    assert response.status_code == 200, response.text

    student = StudentService().get_student_by_roll("S002")
    assert student is not None
    sample_dir = Path(student.face_image_dir)
    assert sample_dir.is_dir()
    assert len(list(sample_dir.glob("sample_*.jpg"))) == 15
    assert tmp_path / "data" in sample_dir.parents


def test_student_registration_rejects_bad_sample_count(client: TestClient) -> None:
    token = _login(client, "admin", "admin123", "admin")
    response = client.post(
        "/api/students/register-with-faces",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "roll_no": "S003",
            "name": "Student Three",
            "department": "Engineering",
            "year": "3",
            "section": "B3",
            "password": "student-password",
            "serialized_encoding": serialize_encodings([np.zeros(128)]),
        },
        files=[("files", ("sample.jpg", _jpeg_bytes(), "image/jpeg"))],
    )
    assert response.status_code == 400
