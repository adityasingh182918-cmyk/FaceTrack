"""FastAPI entrypoint for the FACETRACK backend."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIST_DIR = PROJECT_ROOT / "web_app" / "dist"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_api.app.api import attendance, auth, faculty, health, reports, students, timetable
from database.db import init_database
from backend_api.app.security import validate_auth_configuration


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    validate_auth_configuration()
    init_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="FACETRACK Backend API",
        version="0.1.0",
        description="Shared API layer for FACETRACK desktop and web clients.",
        lifespan=lifespan,
    )
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("FACETRACK_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if os.getenv("FACETRACK_ENV") != "production" and not allowed_origins:
        allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(faculty.router, prefix="/api")
    app.include_router(students.router, prefix="/api")
    app.include_router(timetable.router, prefix="/api")
    app.include_router(attendance.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")

    if WEB_DIST_DIR.exists():
        assets_dir = WEB_DIST_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")

        @app.get("/", include_in_schema=False)
        def serve_web_root() -> FileResponse:
            return FileResponse(WEB_DIST_DIR / "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_web_app(full_path: str) -> FileResponse:
            if full_path.startswith("api/"):
                return FileResponse(WEB_DIST_DIR / "index.html")

            candidate = WEB_DIST_DIR / full_path
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST_DIR / "index.html")

    return app


app = create_app()
