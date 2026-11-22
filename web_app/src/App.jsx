import { useEffect, useState } from "react";
import LoginScreen from "./components/LoginScreen.jsx";
import PortalShell from "./components/PortalShell.jsx";
import StaffPortal from "./components/StaffPortal.jsx";
import { api, setAccessToken } from "./services/api.js";

const STORAGE_KEY = "facetrack-session";

function loadStoredSession(setToken) {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    const session = raw ? JSON.parse(raw) : null;
    if (session?.access_token && session?.user?.role) {
      setToken(session.access_token);
      return session;
    }
    return null;
  } catch {
    return null;
  }
}

export default function App() {
  const [form, setForm] = useState({ username: "", password: "", role: "student" });
  const [session, setSession] = useState(() => loadStoredSession(setAccessToken));
  const [profile, setProfile] = useState(null);
  const [attendanceSummary, setAttendanceSummary] = useState(null);
  const [attendanceRecords, setAttendanceRecords] = useState([]);
  const [timetable, setTimetable] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    function handleUnauthorized() {
      window.sessionStorage.removeItem(STORAGE_KEY);
      setSession(null);
      setProfile(null);
      setAttendanceSummary(null);
      setAttendanceRecords([]);
      setTimetable([]);
      setError("Your session expired. Please sign in again.");
    }

    window.addEventListener("facetrack:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("facetrack:unauthorized", handleUnauthorized);
  }, []);

  useEffect(() => {
    if (session?.user?.role !== "student" || !session.user.roll_no) {
      return;
    }

    let active = true;
    setLoading(true);
    setError("");

    Promise.all([
      api.getStudentProfile(session.user.roll_no),
      api.getStudentAttendanceSummary(session.user.roll_no),
      api.getStudentAttendanceRecords(session.user.roll_no),
    ])
      .then(async ([profileResponse, summaryResponse, attendanceResponse]) => {
        const timetableResponse = await api.getStudentTimetable(profileResponse.section);
        if (!active) {
          return;
        }
        setProfile(profileResponse);
        setAttendanceSummary(summaryResponse);
        setAttendanceRecords(attendanceResponse);
        setTimetable(timetableResponse);
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        setError(requestError.message || "Unable to load student portal.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [session]);

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const username = form.role === "student" ? form.username.trim().toUpperCase() : form.username.trim();
      const response = await api.login(username, form.password, form.role);
      const nextSession = { user: response.user, access_token: response.access_token };
      setAccessToken(response.access_token);
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextSession));
      setSession(nextSession);
      setForm((current) => ({ ...current, username: "", password: "" }));
    } catch (requestError) {
      setError(requestError.message || "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    setAccessToken(null);
    window.sessionStorage.removeItem(STORAGE_KEY);
    setSession(null);
    setProfile(null);
    setAttendanceSummary(null);
    setAttendanceRecords([]);
    setTimetable([]);
    setError("");
  }

  if (!session) {
    return (
      <LoginScreen
        form={form}
        error={error}
        loading={loading}
        onChange={handleChange}
        onSubmit={handleSubmit}
      />
    );
  }

  if (session.user.role !== "student") {
    return <StaffPortal user={session.user} onLogout={handleLogout} />;
  }

  return (
    <PortalShell
      student={session.user}
      profile={profile}
      attendanceSummary={attendanceSummary}
      attendanceRecords={attendanceRecords}
      timetable={timetable}
      loading={loading}
      error={error}
      onLogout={handleLogout}
    />
  );
}
