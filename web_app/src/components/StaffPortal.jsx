import { useEffect, useState } from "react";
import { api } from "../services/api.js";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function Table({ columns, rows, emptyText }) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((row, index) => (
            <tr key={row.id ?? row.roll_no ?? row.username ?? `${index}`}>
              {row.cells.map((cell, cellIndex) => <td key={cellIndex}>{cell ?? "-"}</td>)}
              {row.action ? <td>{row.action}</td> : null}
            </tr>
          )) : (
            <tr><td colSpan={columns.length}>{emptyText}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Field({ label, name, value, onChange, type = "text", required = true, children }) {
  return (
    <label>
      <span>{label}</span>
      {children || (
        <input
          name={name}
          type={type}
          value={value}
          onChange={onChange}
          required={required}
        />
      )}
    </label>
  );
}

export default function StaffPortal({ user, onLogout }) {
  const isAdmin = user.role === "admin";
  const [activeView, setActiveView] = useState("overview");
  const [data, setData] = useState({});
  const [facultyForm, setFacultyForm] = useState({ name: "", username: "", password: "" });
  const [timetableForm, setTimetableForm] = useState({
    subject: "",
    faculty: user.username || "",
    day: "Monday",
    start_time: "",
    end_time: "",
    section: "",
  });
  const [attendanceForm, setAttendanceForm] = useState({ timetableId: "", rollNo: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadView(view = activeView) {
    setError("");
    if (view === "overview") {
      const [students, classes, attendance] = await Promise.all([
        api.listStudents(),
        api.getTodayClasses(),
        api.getAttendance(),
      ]);
      setData({ students, classes, attendance });
      return;
    }
    if (view === "students") {
      setData({ students: await api.listStudents() });
      return;
    }
    if (view === "faculty") {
      setData({ faculty: await api.listFaculty() });
      return;
    }
    if (view === "timetable") {
      setData({ timetable: await api.getTimetable() });
      return;
    }
    if (view === "attendance") {
      const [attendance, classes] = await Promise.all([api.getAttendance(), api.getTodayClasses()]);
      setData({ attendance, classes });
      setAttendanceForm((current) => ({
        ...current,
        timetableId: current.timetableId || String(classes[0]?.id || ""),
      }));
      return;
    }
    if (view === "reports") {
      setData({ reports: await api.getLateFlagReport() });
    }
  }

  useEffect(() => {
    let active = true;
    loadView(activeView).catch((requestError) => {
      if (active) setError(requestError.message || "Unable to load this workspace.");
    });
    return () => { active = false; };
  }, [activeView]);

  async function perform(action, successMessage) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(successMessage);
      await loadView();
      return true;
    } catch (requestError) {
      setError(requestError.message || "The operation failed.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function changeForm(setter) {
    return (event) => {
      const { name, value } = event.target;
      setter((current) => ({ ...current, [name]: value }));
    };
  }

  const menu = [
    ["overview", "Overview"],
    ...(isAdmin ? [["students", "Students"], ["faculty", "Faculty"]] : []),
    ["timetable", "Timetable"],
    ["attendance", "Attendance"],
    ["reports", "Reports"],
  ];

  function renderContent() {
    if (activeView === "students") {
      const rows = (data.students || []).map((student) => ({
        ...student,
        cells: [student.roll_no, student.name, student.department, student.year, student.section, student.red_flags],
        action: (
          <button
            className="table-action danger"
            type="button"
            disabled={busy}
            onClick={() => {
              if (window.confirm(`Delete student ${student.roll_no}? This also removes their attendance and stored face samples.`)) {
                perform(() => api.deleteStudent(student.roll_no), "Student deleted.");
              }
            }}
          >
            Delete
          </button>
        ),
      }));
      return (
        <section className="panel-card wide">
          <div className="panel-head">
            <h3>Student Records</h3>
            <p>Profile management is available here. New face-enabled enrollment and camera capture remain in the desktop registration tool.</p>
          </div>
          <Table
            columns={["Roll Number", "Name", "Department", "Year", "Section", "Red Flags", ""]}
            rows={rows}
            emptyText="No student records are available."
          />
        </section>
      );
    }

    if (activeView === "faculty") {
      const rows = (data.faculty || []).map((faculty) => ({
        ...faculty,
        cells: [faculty.username, faculty.name, faculty.role],
        action: faculty.role === "admin" ? null : (
          <button
            className="table-action danger"
            type="button"
            disabled={busy}
            onClick={() => {
              if (window.confirm(`Delete faculty account ${faculty.username}?`)) {
                perform(() => api.deleteFaculty(faculty.username), "Faculty account deleted.");
              }
            }}
          >
            Delete
          </button>
        ),
      }));
      return (
        <>
          <section className="panel-card">
            <div className="panel-head">
              <h3>Create Faculty Account</h3>
              <p>Passwords are stored as salted PBKDF2 hashes.</p>
            </div>
            <form
              className="staff-form"
              onSubmit={(event) => {
                event.preventDefault();
                perform(
                  () => api.createFaculty(facultyForm),
                  "Faculty account created.",
                ).then((succeeded) => {
                  if (succeeded) setFacultyForm({ name: "", username: "", password: "" });
                });
              }}
            >
              <Field label="Name" name="name" value={facultyForm.name} onChange={changeForm(setFacultyForm)} />
              <Field label="Username" name="username" value={facultyForm.username} onChange={changeForm(setFacultyForm)} />
              <Field label="Initial password" name="password" type="password" value={facultyForm.password} onChange={changeForm(setFacultyForm)} />
              <button className="primary-button" disabled={busy}>Create Account</button>
            </form>
          </section>
          <section className="panel-card wide">
            <div className="panel-head"><h3>Faculty Accounts</h3></div>
            <Table columns={["Username", "Name", "Role", ""]} rows={rows} emptyText="No faculty accounts are available." />
          </section>
        </>
      );
    }

    if (activeView === "timetable") {
      const rows = (data.timetable || []).map((entry) => ({
        ...entry,
        cells: [entry.subject, entry.faculty, entry.day, `${entry.start_time}–${entry.end_time}`, entry.section],
        action: isAdmin ? (
          <button
            className="table-action danger"
            type="button"
            disabled={busy}
            onClick={() => {
              if (window.confirm(`Delete ${entry.subject} from ${entry.section}'s timetable?`)) {
                perform(() => api.deleteTimetable(entry.id), "Timetable entry deleted.");
              }
            }}
          >
            Delete
          </button>
        ) : null,
      }));
      return (
        <>
          {isAdmin ? (
            <section className="panel-card">
              <div className="panel-head"><h3>Add Timetable Entry</h3></div>
              <form
                className="staff-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  perform(() => api.createTimetable(timetableForm), "Timetable entry created.");
                }}
              >
                <Field label="Subject" name="subject" value={timetableForm.subject} onChange={changeForm(setTimetableForm)} />
                <Field label="Faculty username" name="faculty" value={timetableForm.faculty} onChange={changeForm(setTimetableForm)} />
                <Field label="Day" name="day" value={timetableForm.day} onChange={changeForm(setTimetableForm)}>
                  <select name="day" value={timetableForm.day} onChange={changeForm(setTimetableForm)}>
                    {DAYS.map((day) => <option key={day}>{day}</option>)}
                  </select>
                </Field>
                <Field label="Start time" name="start_time" type="time" value={timetableForm.start_time} onChange={changeForm(setTimetableForm)} />
                <Field label="End time" name="end_time" type="time" value={timetableForm.end_time} onChange={changeForm(setTimetableForm)} />
                <Field label="Section" name="section" value={timetableForm.section} onChange={changeForm(setTimetableForm)} />
                <button className="primary-button" disabled={busy}>Add Entry</button>
              </form>
            </section>
          ) : null}
          <section className="panel-card wide">
            <div className="panel-head"><h3>{isAdmin ? "Published Timetable" : "My Assigned Timetable"}</h3></div>
            <Table columns={["Subject", "Faculty", "Day", "Time", "Section", ...(isAdmin ? [""] : [])]} rows={rows} emptyText="No timetable entries are available." />
          </section>
        </>
      );
    }

    if (activeView === "attendance") {
      const classOptions = data.classes || [];
      const rows = (data.attendance || []).map((record) => ({
        ...record,
        cells: [record.date, record.time, record.roll_no, record.name, record.subject, record.status, record.late_flags],
      }));
      return (
        <>
          <section className="panel-card">
            <div className="panel-head">
              <h3>Attendance Session</h3>
              <p>Faculty may prepare absent records and mark a student from an assigned class. Camera recognition remains available in the desktop app.</p>
            </div>
            <form
              className="staff-form"
              onSubmit={(event) => {
                event.preventDefault();
                perform(() => api.markAttendance(Number(attendanceForm.timetableId), attendanceForm.rollNo.trim().toUpperCase()), "Attendance marked.");
              }}
            >
              <Field label="Today's class" name="timetableId" value={attendanceForm.timetableId} onChange={changeForm(setAttendanceForm)}>
                <select
                  name="timetableId"
                  value={attendanceForm.timetableId}
                  onChange={changeForm(setAttendanceForm)}
                  required
                >
                  {classOptions.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.subject} · {entry.section} · {entry.start_time}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Student roll number" name="rollNo" value={attendanceForm.rollNo} onChange={changeForm(setAttendanceForm)} />
              <div className="button-row">
                <button className="primary-button" disabled={busy || !classOptions.length}>Mark Present</button>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={busy || !classOptions.length}
                  onClick={() => perform(
                    () => api.seedAttendance(Number(attendanceForm.timetableId)),
                    "Absent records prepared for this class.",
                  )}
                >
                  Prepare Class
                </button>
              </div>
            </form>
          </section>
          <section className="panel-card wide">
            <div className="panel-head"><h3>Attendance History</h3></div>
            <Table
              columns={["Date", "Time", "Roll Number", "Name", "Subject", "Status", "Late Flags"]}
              rows={rows}
              emptyText="No attendance records are available."
            />
          </section>
        </>
      );
    }

    if (activeView === "reports") {
      const rows = (data.reports || []).map((record) => ({
        ...record,
        cells: [record.roll_no, record.name, record.section, record.red_flags, record.total_late_flags],
      }));
      return (
        <section className="panel-card wide">
          <div className="panel-head"><h3>Late Flag Report</h3><p>Faculty see students in their assigned sections; administrators see all students.</p></div>
          <Table columns={["Roll Number", "Name", "Section", "Current Flags", "Total Late Flags"]} rows={rows} emptyText="No late-flag records are available." />
        </section>
      );
    }

    return (
      <>
        <section className="hero-strip">
          <div>
            <p className="eyebrow">{isAdmin ? "ADMINISTRATOR WORKSPACE" : "FACULTY WORKSPACE"}</p>
            <h2>Welcome, {user.name}</h2>
            <p className="hero-copy">
              {isAdmin
                ? "Manage academic records, faculty access, timetables, and system reports."
                : "Review assigned classes and manage attendance for your sections."}
            </p>
          </div>
        </section>
        <section className="content-grid">
          {[
            ["Students in scope", (data.students || []).length],
            ["Today's classes", (data.classes || []).length],
            ["Attendance records", (data.attendance || []).length],
          ].map(([label, value]) => (
            <div className="info-card" key={label}><p>{label}</p><h3>{value}</h3></div>
          ))}
        </section>
      </>
    );
  }

  return (
    <div className="portal-page staff-page">
      <aside className="portal-sidebar">
        <div>
          <div className="logo-badge large">FT</div>
          <h1>FACETRACK</h1>
          <p className="sidebar-copy">{user.role === "admin" ? "Administrator" : "Faculty"} workspace</p>
        </div>
        <div className="sidebar-card">
          <p className="sidebar-label">Signed in as</p>
          <h3>{user.name}</h3>
          <p>{user.username}</p>
          <p>Role: {user.role}</p>
        </div>
        <nav className="sidebar-menu">
          {menu.map(([key, label]) => (
            <button
              key={key}
              className={`menu-button${activeView === key ? " active" : ""}`}
              onClick={() => setActiveView(key)}
              type="button"
            >
              {label}
            </button>
          ))}
        </nav>
        <button className="secondary-button" onClick={onLogout} type="button">Logout</button>
      </aside>
      <main className="portal-main">
        {error ? <div className="error-banner">{error}</div> : null}
        {notice ? <div className="notice-banner">{notice}</div> : null}
        {busy ? <div className="loading-banner">Saving changes...</div> : null}
        {renderContent()}
      </main>
    </div>
  );
}
