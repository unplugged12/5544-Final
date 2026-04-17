import { useState, useEffect } from "react";
import {
  healthCheck,
  getDemoMode,
  setDemoMode,
  getAllSettings,
  updateSettings,
} from "../api.js";
import "./Settings.css";

// Integer fields and their validation bounds
const INT_FIELDS = {
  discipline_points_threshold: { min: 1, max: 100 },
  discipline_window_days: { min: 1, max: 365 },
  discipline_ban_minutes: { min: 1, max: 43200 }, // up to 30 days
};

function asBool(v) {
  return v === "true" || v === true;
}

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [demoMode, setDemoModeState] = useState(false);
  const [toggling, setToggling] = useState(false);

  const [settings, setSettings] = useState(null);
  const [dirty, setDirty] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([healthCheck(), getDemoMode(), getAllSettings()])
      .then(([h, d, s]) => {
        setHealth(h);
        setDemoModeState(d.demo_mode);
        setSettings(s.settings);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleToggleDemo = async () => {
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

  const currentValue = (key) => {
    if (key in dirty) return dirty[key];
    return settings?.[key] ?? "";
  };

  const setField = (key, value) => {
    setDirty((d) => ({ ...d, [key]: value }));
    setSaveMsg("");
  };

  const validate = () => {
    for (const [key, { min, max }] of Object.entries(INT_FIELDS)) {
      if (!(key in dirty)) continue;
      const raw = dirty[key];
      const n = Number(raw);
      if (!Number.isInteger(n) || n < min || n > max) {
        return `${key} must be an integer between ${min} and ${max}`;
      }
    }
    return null;
  };

  const handleSave = async () => {
    const err = validate();
    if (err) {
      setSaveMsg(err);
      return;
    }
    setSaving(true);
    setSaveMsg("");
    try {
      const res = await updateSettings(dirty);
      setSettings(res.settings);
      setDirty({});
      setSaveMsg("Saved.");
    } catch (e) {
      setSaveMsg(e.message || "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = Object.keys(dirty).length > 0;

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
            onClick={handleToggleDemo}
            disabled={toggling}
          >
            {demoMode ? "ON" : "OFF"}
          </button>
        </div>
      </div>

      {settings && (
        <div className="settings__section">
          <h3 className="settings__section-title">Progressive Discipline</h3>

          <div className="settings__row">
            <div className="settings__row-info">
              <p className="settings__label">Test Mode</p>
              <p className="settings__description">
                Dry-run — discipline decisions are recorded and surfaced in alerts, but
                no kick or ban is sent to Discord. Useful for verifying policy changes.
              </p>
            </div>
            <button
              className={`settings__toggle ${asBool(currentValue("test_mode")) ? "settings__toggle--on" : ""}`}
              onClick={() => setField("test_mode", asBool(currentValue("test_mode")) ? "false" : "true")}
              disabled={saving}
            >
              {asBool(currentValue("test_mode")) ? "ON" : "OFF"}
            </button>
          </div>

          <div className="settings__row settings__row--stacked">
            <div className="settings__row-info">
              <p className="settings__label">Repeat-category kicks</p>
              <p className="settings__description">
                Kick a user on a second offense in the same rule category within the
                rolling window, even if their point total is below the threshold.
              </p>
            </div>
            <button
              className={`settings__toggle ${asBool(currentValue("discipline_repeat_category_kicks")) ? "settings__toggle--on" : ""}`}
              onClick={() => setField(
                "discipline_repeat_category_kicks",
                asBool(currentValue("discipline_repeat_category_kicks")) ? "false" : "true",
              )}
              disabled={saving}
            >
              {asBool(currentValue("discipline_repeat_category_kicks")) ? "ON" : "OFF"}
            </button>
          </div>

          <div className="settings__grid settings__grid--inputs">
            <label className="settings__field">
              <span className="settings__field-label">Points threshold (kick)</span>
              <input
                className="settings__input"
                type="number"
                min="1"
                max="100"
                value={currentValue("discipline_points_threshold")}
                onChange={(e) => setField("discipline_points_threshold", e.target.value)}
                disabled={saving}
              />
              <span className="settings__field-hint">Severity points: low=1, med=2, high=3, crit=5</span>
            </label>

            <label className="settings__field">
              <span className="settings__field-label">Rolling window (days)</span>
              <input
                className="settings__input"
                type="number"
                min="1"
                max="365"
                value={currentValue("discipline_window_days")}
                onChange={(e) => setField("discipline_window_days", e.target.value)}
                disabled={saving}
              />
              <span className="settings__field-hint">Older violations decay out of the ledger</span>
            </label>

            <label className="settings__field">
              <span className="settings__field-label">Timed ban (minutes)</span>
              <input
                className="settings__input"
                type="number"
                min="1"
                max="43200"
                value={currentValue("discipline_ban_minutes")}
                onChange={(e) => setField("discipline_ban_minutes", e.target.value)}
                disabled={saving}
              />
              <span className="settings__field-hint">Applied when a kicked user re-offends</span>
            </label>
          </div>

          <div className="settings__actions">
            <button
              className="settings__save-btn"
              onClick={handleSave}
              disabled={!hasChanges || saving}
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
            {saveMsg && (
              <span
                className={`settings__save-msg ${saveMsg === "Saved." ? "settings__save-msg--ok" : "settings__save-msg--err"}`}
              >
                {saveMsg}
              </span>
            )}
          </div>
        </div>
      )}

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
