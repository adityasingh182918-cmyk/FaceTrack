# FACETRACK

University Face Attendance System

FACETRACK is a desktop ERP-style identity and attendance system for faculty-driven student attendance using face recognition. Faculty controls student registration, timetable management, and attendance sessions. Students get read-only access to profile, timetable, and attendance analytics.

## Features

- Role-based login for admin, faculty, and students
- Admin-managed faculty registration and timetable assignment
- Faculty-controlled attendance sessions for assigned classes only
- Student registration with webcam face sample capture
- Embedding-based student recognition with Euclidean distance matching
- Weekly timetable creation and today-class attendance workflow
- Duplicate attendance prevention
- Faculty reports with CSV export
- Student dashboard with profile, timetable, and attendance percentage
- SQLite persistence and file logging

## Project Structure

```text
FACETRACK/
|-- main.py
|-- setup_database.py
|-- backend_api/
|   |-- app/
|   |-- requirements.txt
|   |-- README.md
|-- web_app/
|   |-- src/
|   |-- package.json
|   |-- README.md
|-- gui/
|   |-- login_window.py
|   |-- faculty_dashboard.py
|   |-- student_dashboard.py
|   |-- register_student.py
|   |-- attendance_page.py
|   |-- timetable_page.py
|-- face_engine/
|   |-- face_capture.py
|   |-- face_encode.py
|   |-- face_recognizer.py
|-- database/
|   |-- db.py
|   |-- models.py
|-- services/
|   |-- attendance_service.py
|   |-- timetable_service.py
|   |-- student_service.py
|   |-- faculty_service.py
|-- utils/
|   |-- config.py
|   |-- helpers.py
|-- data/
|   |-- faces/
|   |-- database.db
|-- requirements.txt
```

## Setup

1. Install Git LFS before cloning or pulling the repository assets:

```bash
git lfs install
```

If Git LFS is not installed on your machine yet, download it from [git-lfs.com](https://git-lfs.com/) and then run the command above once.

2. Clone the repository:

```bash
git clone https://github.com/Mohakkalra03/FaceTrack.git
cd FaceTrack
```

3. Create and activate a virtual environment.
4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Optional database bootstrap:

```bash
python setup_database.py
```

6. Run the application:

```bash
python main.py
```

7. Run the shared backend API from the project root if you want desktop + web integration:

```bash
python api_server.py
```

## One-Click Launchers

- Double-click [start_facetrack_desktop.bat](C:/Users/DELL/OneDrive/Desktop/Sem4/DTI/start_facetrack_desktop.bat) to start backend + desktop app together.
- Run [build_web_app.bat](C:/Users/DELL/OneDrive/Desktop/Sem4/DTI/build_web_app.bat) once to create the production web bundle.
- Double-click [start_facetrack_mobile.bat](C:/Users/DELL/OneDrive/Desktop/Sem4/DTI/start_facetrack_mobile.bat) to expose the built web portal on your local Wi-Fi.

## EXE Builds

- Run [build_desktop_exe.bat](C:/Users/DELL/OneDrive/Desktop/Sem4/DTI/build_desktop_exe.bat) to create `dist\FACETRACK\FACETRACK.exe`
- Run [build_portal_exe.bat](C:/Users/DELL/OneDrive/Desktop/Sem4/DTI/build_portal_exe.bat) to create `dist\FACETRACK-Portal\FACETRACK-Portal.exe`
- Run [start_portal_exe.bat](C:/Users/DELL/OneDrive/Desktop/Sem4/DTI/start_portal_exe.bat) after building the portal exe to serve the student portal for phone access on your local Wi-Fi

## Default Admin Login

- Username: `admin`
- Password: `admin123`

## Public Web Deployment (Vercel + Render)

The browser portal is the Vite/React application in `web_app/` (`npm run build`, output `web_app/dist`). Its API client uses `VITE_API_BASE_URL`; local development defaults to `/api` and Vite proxies that path to the API. In production, the frontend calls the Render API directly. The root `vercel.json` publishes only the `web_app` service; the FastAPI API is not deployed to Vercel.

The FastAPI entry point is `backend_api.app.main:app`, with its HTTP routes under `/api`. Deploy it from the repository root using the included `render.yaml`. The Render service uses `backend_api/requirements.txt`, runs one paid instance, and mounts persistent storage at `/var/data`. SQLite, uploaded face samples, and logs use that directory. The disk keeps data between deploys but is single-instance storage: it does not support horizontal scaling or zero-downtime deploys. Back up the disk and database. For multi-instance scaling, migrate to managed PostgreSQL and object storage.

### Deploy

1. Push this repository to GitHub and import it into Vercel. Keep the repository root as the project root so Vercel reads `vercel.json`. The frontend declares Node.js `>=22.12.0` for its Vite toolchain. Deploy once to create the production Vercel domain; API-backed sign-in will not work until the backend is connected.
2. Create a Render Blueprint from the same GitHub repository so Render reads `render.yaml`. When prompted for `FACETRACK_ALLOWED_ORIGINS`, enter the production Vercel origin (for example, `https://your-project.vercel.app`, without a trailing slash). Include a custom domain too if you use one, separated by commas. The blueprint generates `FACETRACK_ADMIN_PASSWORD` and `FACETRACK_JWT_SECRET`; keep both private. Wait for the service health check at `/api/health` to pass.
3. In Vercel project settings, add `VITE_API_BASE_URL` with the actual Render API URL ending in `/api`, for example `https://facetrack-api.onrender.com/api`, then redeploy the frontend. Vercel preview URLs are not allowed by default; add a specific preview origin to Render's `FACETRACK_ALLOWED_ORIGINS` only if needed.
4. Retrieve the generated admin password from the private Render service environment and sign in to the website as `admin`. For desktop enrollment and recognition against this deployment, configure the desktop machine with `FACETRACK_BACKEND_API_ENABLED=1` and `FACETRACK_BACKEND_API_URL=https://facetrack-api.onrender.com/api`. Do not put backend secrets in Vercel variables or commit them to GitHub.
5. Add faculty/timetables in the administrator portal. Student enrollment with captured face samples remains available in the desktop app. The web portal supports student, faculty, and admin sign-in and attendance administration, but it does not access a browser camera or perform face recognition. Recognition remains in the desktop application, which sends the resulting encodings and face samples to the API.

### Data and runtime limits

- The deployment starts with a new SQLite database. Existing local student/faculty records, attendance, and face images are not in Git and are not migrated automatically. Back up and securely transfer them to the Render disk before switching users to the hosted service.
- Render's persistent disk preserves SQLite and uploaded face files, but the service must remain single-instance. SQLite is not appropriate for concurrent multi-instance deployment.
- PyQt6 windows and direct local camera access cannot run as a Vercel website. The web app is a separate portal; face capture/recognition is still performed by the desktop app.
- The backend deliberately requires production admin-password, JWT-secret, and CORS-origin settings. Render provisions the first two; set the actual Vercel origin in Render before inviting users.
- `FACETRACK_BACKEND_API_URL` for the desktop client includes `/api`. The separate `FACETRACK_DEV_API_TARGET` used by Vite is just the backend origin, without `/api`.

### Local web/API development

Run `python api_server.py` from the repository root, then in another terminal run `npm ci` and `npm run dev` from `web_app/` using Node.js `>=22.12.0`. The Vite proxy forwards `/api` to `http://127.0.0.1:8000` by default; override it with `FACETRACK_DEV_API_TARGET` if needed. Local-only development retains the default `admin` / `admin123` account. Never use that password in production.

## Notes

- `face_recognition` is used when available. If it is not installed successfully on the local machine, FACETRACK falls back to a simplified OpenCV-based embedding mode so the application still runs for demonstration and testing.
- Attendance can only be started by faculty after selecting one of today's timetable classes.
- Student accounts cannot create attendance, alter timetable data, or modify institutional records.
- A shared backend scaffold now exists in [backend_api/README.md](C:/Users/DELL/OneDrive/Desktop/Sem4/DTI/backend_api/README.md) for future desktop + web architecture.
- A first student web portal scaffold now exists in [web_app/README.md](C:/Users/DELL/OneDrive/Desktop/Sem4/DTI/web_app/README.md).
- The desktop app now prefers backend API reads for login, dashboard summaries, reports, and read-only timetable/student views when the backend is running, and falls back to local services if the backend is unavailable.
- A permanent public website link is not something the local machine can create by itself; that requires external hosting or a domain. The current project now supports a one-click local-network mobile link from your laptop.
- The desktop executable and portal executable require PyInstaller, which is installed automatically by the provided build scripts.
