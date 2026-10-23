import { Link, NavLink, Outlet } from "react-router-dom";
import { useRecordingSession } from "../hooks/useRecordingSession";
import { useTheme } from "../hooks/useTheme";
import Icon from "./Icon";
import Logo from "./Logo";

export default function Layout() {
  const { live, saving } = useRecordingSession();
  const recording = live.status === "recording";
  const working = live.status === "connecting" || live.status === "finishing" || saving;
  const { theme, toggle } = useTheme();
  const themeLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <div className="shell">
      <header className="appbar">
        <button className="icon-btn theme-toggle" onClick={toggle} aria-label={themeLabel} title={themeLabel}>
          <Icon name={theme === "dark" ? "lightMode" : "darkMode"} />
        </button>
        <Link to="/" className="appbar-logo" aria-label="Vaani home">
          <Logo />
        </Link>
        <p className="tagline">Speak in your language, or mix a few.</p>
      </header>
      <nav className="tabs" aria-label="Sections">
        <NavLink to="/" end className="tab">
          <Icon name="mic" size={18} />
          Record
          {(recording || working) && (
            <span
              className={`tab-badge ${recording ? "is-recording" : ""}`}
              title={recording ? "Recording" : "Saving"}
              aria-label={recording ? "Recording" : "Saving"}
            />
          )}
        </NavLink>
        <NavLink to="/dashboard" className="tab">
          <Icon name="history" size={18} />
          History
        </NavLink>
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
