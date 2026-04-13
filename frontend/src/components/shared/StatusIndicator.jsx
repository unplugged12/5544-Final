import "./StatusIndicator.css";

export default function StatusIndicator({ demoMode, onToggle }) {
  return (
    <div className="status-indicator">
      <span
        className={`status-indicator__dot ${
          demoMode ? "status-indicator__dot--demo" : "status-indicator__dot--live"
        }`}
      />
      <span className="status-indicator__label">
        {demoMode ? "DEMO MODE" : "LIVE MODE"}
      </span>
      <button
        className={`status-indicator__toggle ${
          demoMode ? "status-indicator__toggle--on" : ""
        }`}
        onClick={onToggle}
        aria-label={demoMode ? "Switch to live mode" : "Switch to demo mode"}
      >
        <span className="status-indicator__toggle-knob" />
      </button>
    </div>
  );
}
