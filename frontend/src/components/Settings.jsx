import { useState, useEffect } from "react";
import { healthCheck, getDemoMode, setDemoMode } from "../api.js";
import "./Settings.css";

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [demoMode, setDemoModeState] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    Promise.all([healthCheck(), getDemoMode()])
      .then(([h, d]) => {
        setHealth(h);
        setDemoModeState(d.demo_mode);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async () => {
    setToggling(true);
    try {
      const res = await setDemoMode(!demoMode);
      setDemoModeState(res.demo_mode);
    } catch {
      // Silently fail
    } finally {
      setToggling(false);
    }
  };

  if (loading) {
    return <div className="settings"><p className="settings__loading">Loading settings...</p></div>;
  }

  return (
    <div className="settings">
      <h2 className="settings__title">Settings</h2>

      <div className="settings__section">
        <h3 className="settings__section-title">Demo Mode</h3>
        <div className="settings__row">
          <div className="settings__row-info">
            <p className="settings__label">Auto-delete mode</p>
            <p className="settings__description">
              When enabled, clear rule violations in the sandbox channel are automatically
              deleted. When disabled, violations are flagged for moderator review.
            </p>
          </div>
          <button
            className={`settings__toggle ${demoMode ? "settings__toggle--on" : ""}`}
            onClick={handleToggle}
            disabled={toggling}
          >
            {demoMode ? "ON" : "OFF"}
          </button>
        </div>
      </div>

      {health && (
        <div className="settings__section">
          <h3 className="settings__section-title">System Status</h3>
          <div className="settings__grid">
            <div className="settings__stat">
              <span className="settings__stat-label">Status</span>
              <span className="settings__stat-value settings__stat-value--ok">
                {health.status}
              </span>
            </div>
            <div className="settings__stat">
              <span className="settings__stat-label">Primary Provider</span>
              <span className="settings__stat-value">{health.provider || "openai"}</span>
            </div>
            <div className="settings__stat">
              <span className="settings__stat-label">Knowledge Items</span>
              <span className="settings__stat-value">{health.knowledge_count ?? "—"}</span>
            </div>
            <div className="settings__stat">
              <span className="settings__stat-label">Demo Mode</span>
              <span className={`settings__stat-value ${demoMode ? "settings__stat-value--warn" : "settings__stat-value--ok"}`}>
                {demoMode ? "Enabled" : "Disabled"}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="settings__section">
        <h3 className="settings__section-title">About</h3>
        <p className="settings__description">
          Esports Community Mod + FAQ Copilot — Proof of Concept.
          Built with FastAPI, React, discord.py, and Chroma vector retrieval.
          Seeded with CDL Ranked Discord community data for Call of Duty: Black Ops 7.
        </p>
      </div>
    </div>
  );
}
