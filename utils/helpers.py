"""Shared helper utilities for FACETRACK."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime
from typing import TYPE_CHECKING, Iterable

import numpy as np

if TYPE_CHECKING:
    from PyQt6.QtGui import QPixmap

from utils.config import LOG_FILE, LOGS_DIR


def setup_logging() -> None:
    """Configure file logging once for the application."""
    if logging.getLogger().handlers:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


_PASSWORD_HASH_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 password hash."""
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_HASH_ITERATIONS)
    return f"pbkdf2_sha256${_PASSWORD_HASH_ITERATIONS}${salt.hex()}${password_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify current PBKDF2 hashes and legacy SHA-256 hashes."""
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iteration_count, salt_hex, hash_hex = stored_hash.split("$", 3)
            iterations = int(iteration_count)
            if iterations < 1:
                return False
            actual_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations)
            return hmac.compare_digest(actual_hash.hex(), hash_hex)
        except (ValueError, TypeError):
            return False

    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)


def password_needs_rehash(stored_hash: str) -> bool:
    """Identify legacy or weaker hashes for gradual login-time migration."""
    if not stored_hash.startswith("pbkdf2_sha256$"):
        return True
    try:
        _, iteration_count, _, _ = stored_hash.split("$", 3)
        return int(iteration_count) < _PASSWORD_HASH_ITERATIONS
    except (ValueError, TypeError):
        return True


def serialize_encodings(encodings: Iterable[np.ndarray]) -> str:
    """Serialize numpy encodings into a storable string."""
    payload = [base64.b64encode(np.asarray(item, dtype=np.float64).tobytes()).decode("ascii") for item in encodings]
    return json.dumps(payload)


def deserialize_encodings(raw_value: str | None) -> list[np.ndarray]:
    """Deserialize facial encodings stored in the database."""
    if not raw_value:
        return []

    values = json.loads(raw_value)
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError("Serialized encodings must be a list of base64 strings.")
    return [np.frombuffer(base64.b64decode(item.encode("ascii")), dtype=np.float64) for item in values]


def current_day_name() -> str:
    """Return the current weekday name."""
    return datetime.now().strftime("%A")


def today_date_str() -> str:
    """Return the current date string."""
    return datetime.now().strftime("%Y-%m-%d")


def now_time_str() -> str:
    """Return the current time string."""
    return datetime.now().strftime("%H:%M:%S")


def frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    """Convert a BGR OpenCV frame to a Qt pixmap."""
    import cv2
    from PyQt6.QtGui import QImage, QPixmap

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channel = rgb_frame.shape
    bytes_per_line = channel * width
    image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image)


def safe_percentage(present: int, total: int) -> float:
    """Avoid division by zero while calculating percentages."""
    if total <= 0:
        return 0.0
    return round((present / total) * 100, 2)
