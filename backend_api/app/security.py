"""Signed access tokens and role-based API dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer_scheme = HTTPBearer(auto_error=False)
_DEVELOPMENT_SECRET = "local-development-secret-do-not-use-in-production"


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    role: str
    username: str | None = None
    roll_no: str | None = None
    section: str | None = None


def _secret_key() -> str:
    secret = os.getenv("FACETRACK_JWT_SECRET")
    if secret:
        if len(secret) < 32:
            raise RuntimeError("FACETRACK_JWT_SECRET must contain at least 32 characters.")
        return secret
    if os.getenv("FACETRACK_ENV") == "production":
        raise RuntimeError("FACETRACK_JWT_SECRET must be configured in production.")
    return _DEVELOPMENT_SECRET


def _is_valid_production_origin(origin: str) -> bool:
    parsed = urlsplit(origin)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
        and not parsed.username
        and not parsed.password
    )


def validate_auth_configuration() -> None:
    _secret_key()
    if os.getenv("FACETRACK_ENV") == "production":
        admin_password = os.getenv("FACETRACK_ADMIN_PASSWORD", "")
        if len(admin_password) < 12:
            raise RuntimeError("FACETRACK_ADMIN_PASSWORD must contain at least 12 characters in production.")
        origins = [
            origin.strip()
            for origin in os.getenv("FACETRACK_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ]
        if not origins or "*" in origins or any(not _is_valid_production_origin(origin) for origin in origins):
            raise RuntimeError("Set FACETRACK_ALLOWED_ORIGINS to the deployed frontend origin.")


def create_access_token(user: dict[str, object]) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
    claims = {
        "sub": f"{user['role']}:{user.get('username') or user.get('roll_no')}",
        "user_id": user["id"],
        "role": user["role"],
        "username": user.get("username"),
        "roll_no": user.get("roll_no"),
        "section": user.get("section"),
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
        "iss": "facetrack",
    }
    return jwt.encode(claims, _secret_key(), algorithm="HS256")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            _secret_key(),
            algorithms=["HS256"],
            issuer="facetrack",
        )
        role = claims.get("role")
        user_id = claims.get("user_id")
        if role not in {"admin", "faculty", "student"} or not isinstance(user_id, int):
            raise jwt.InvalidTokenError("Invalid user claims.")
        return AuthenticatedUser(
            id=user_id,
            role=role,
            username=claims.get("username"),
            roll_no=claims.get("roll_no"),
            section=claims.get("section"),
        )
    except (jwt.InvalidTokenError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_roles(*roles: str) -> Callable:
    def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        return user

    return dependency
