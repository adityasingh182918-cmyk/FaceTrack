export default function LoginScreen({
  form,
  error,
  loading,
  onChange,
  onSubmit,
}) {
  const isStudent = form.role === "student";
  const portalName = isStudent ? "Student" : form.role === "admin" ? "Administrator" : "Faculty";

  return (
    <div className="login-shell">
      <section className="hero-panel">
        <div className="hero-overlay" />
        <div className="hero-content">
          <p className="eyebrow">FACETRACK PORTAL</p>
          <h1>Attendance, timetables, and student records in one place.</h1>
          <p className="hero-copy">
            Sign in to the student, faculty, or administrator workspace. Face
            capture and recognition continue to use the FACETRACK desktop app.
          </p>
        </div>
      </section>

      <section className="login-card">
        <div className="logo-row">
          <div className="logo-badge">FT</div>
          <div>
            <h2>{portalName} Sign In</h2>
            <p>Use your registered {isStudent ? "roll number" : "username"} and password.</p>
          </div>
        </div>

        <form className="form-grid" onSubmit={onSubmit}>
          <label>
            <span>Portal</span>
            <select name="role" value={form.role} onChange={onChange}>
              <option value="student">Student</option>
              <option value="faculty">Faculty</option>
              <option value="admin">Administrator</option>
            </select>
          </label>

          <label>
            <span>{isStudent ? "Roll Number" : "Username"}</span>
            <input
              name="username"
              value={form.username}
              onChange={onChange}
              placeholder={isStudent ? "S24CSEU0001" : "Enter username"}
              autoComplete="username"
            />
          </label>

          <label>
            <span>Password</span>
            <input
              type="password"
              name="password"
              value={form.password}
              onChange={onChange}
              placeholder="Enter password"
              autoComplete="current-password"
            />
          </label>

          {error ? <div className="error-banner">{error}</div> : null}

          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "Signing in..." : `Open ${portalName} Portal`}
          </button>
        </form>
      </section>
    </div>
  );
}
