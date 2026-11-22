const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/+$/, "");
let accessToken = null;

export function setAccessToken(token) {
  accessToken = token;
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers ?? {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401 && accessToken) {
      setAccessToken(null);
      window.dispatchEvent(new Event("facetrack:unauthorized"));
    }
    let detail = "Request failed.";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return response.json();
}

export const api = {
  login(username, password, role) {
    return request("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username,
        password,
        role,
      }),
    });
  },
  listFaculty() {
    return request("/faculty");
  },
  createFaculty(payload) {
    return request("/faculty", { method: "POST", body: JSON.stringify(payload) });
  },
  deleteFaculty(username) {
    return request(`/faculty/${encodeURIComponent(username)}`, { method: "DELETE" });
  },
  listStudents() {
    return request("/students");
  },
  createStudent(payload) {
    return request("/students", { method: "POST", body: JSON.stringify(payload) });
  },
  updateStudent(rollNo, payload) {
    return request(`/students/${encodeURIComponent(rollNo)}`, { method: "PUT", body: JSON.stringify(payload) });
  },
  deleteStudent(rollNo) {
    return request(`/students/${encodeURIComponent(rollNo)}`, { method: "DELETE" });
  },
  getStudentProfile(rollNo) {
    return request(`/students/${encodeURIComponent(rollNo)}`);
  },
  getStudentAttendanceSummary(rollNo) {
    return request(`/students/${encodeURIComponent(rollNo)}/attendance-summary`);
  },
  getStudentAttendanceRecords(rollNo) {
    return request(`/attendance?roll_no=${encodeURIComponent(rollNo)}`);
  },
  getStudentTimetable(section) {
    return request(`/timetable?section=${encodeURIComponent(section)}`);
  },
  getTimetable() {
    return request("/timetable");
  },
  getTodayClasses() {
    return request("/timetable/today");
  },
  createTimetable(payload) {
    return request("/timetable", { method: "POST", body: JSON.stringify(payload) });
  },
  updateTimetable(entryId, payload) {
    return request(`/timetable/${entryId}`, { method: "PUT", body: JSON.stringify({ ...payload, id: entryId }) });
  },
  deleteTimetable(entryId) {
    return request(`/timetable/${entryId}`, { method: "DELETE" });
  },
  getAttendance() {
    return request("/attendance");
  },
  seedAttendance(timetableId) {
    return request("/attendance/session/seed", {
      method: "POST",
      body: JSON.stringify({ timetable_id: timetableId }),
    });
  },
  markAttendance(timetableId, rollNo) {
    return request("/attendance/mark", {
      method: "POST",
      body: JSON.stringify({ timetable_id: timetableId, roll_no: rollNo }),
    });
  },
  getLateFlagReport() {
    return request("/reports/late-flags");
  },
};
