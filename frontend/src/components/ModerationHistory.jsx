import { useState, useEffect, useCallback } from "react";
import { getHistory } from "../api.js";
import SeverityBadge from "./shared/SeverityBadge.jsx";
import RuleMatchChip from "./shared/RuleMatchChip.jsx";
import "./ModerationHistory.css";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
  { key: "pending", label: "Pending" },
  { key: "auto_actioned", label: "Auto-Actioned" },
];

function formatTimestamp(ts) {
  if (!ts) return "--";
  try {
    const d = new Date(ts);
    return d.toLocaleString();
  } catch {
    return ts;
  }
}

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.substring(0, len) + "..." : str;
}

function getStatusClass(status) {
  switch (status) {
    case "approved":
      return "history-status--approved";
    case "rejected":
      return "history-status--rejected";
    case "pending":
      return "history-status--pending";
    case "auto_actioned":
      return "history-status--auto";
    default:
      return "";
  }
}

export default function ModerationHistory() {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeFilter, setActiveFilter] = useState("all");
  const [expandedId, setExpandedId] = useState(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getHistory(200, 0);
      setEvents(result.events || []);
      setTotal(result.total || 0);
    } catch (err) {
      setError(err.message || "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const filteredEvents =
    activeFilter === "all"
      ? events
      : events.filter((e) => e.status === activeFilter);

  const toggleExpand = (eventId) => {
    setExpandedId(expandedId === eventId ? null : eventId);
  };

  return (
    <div className="moderation-history">
      <div className="moderation-history__header">
        <div>
          <h2 className="moderation-history__title">Moderation History</h2>
          <p className="moderation-history__subtitle">
            Browse past moderation events and their outcomes.
            {total > 0 && (
              <span className="moderation-history__count">
                {" "}({total} total)
              </span>
            )}
          </p>
        </div>
        <button
          className="moderation-history__refresh-btn"
          onClick={fetchHistory}
          disabled={loading}
        >
          Refresh
        </button>
      </div>

      <div className="moderation-history__filters">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            className={`moderation-history__filter-btn ${
              activeFilter === f.key
                ? "moderation-history__filter-btn--active"
                : ""
            }`}
            onClick={() => setActiveFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <div className="moderation-history__error">{error}</div>}

      {loading && (
        <div className="moderation-history__loading">Loading history...</div>
      )}

      {!loading && !error && filteredEvents.length === 0 && (
        <div className="moderation-history__empty">No events found.</div>
      )}

      {!loading && !error && filteredEvents.length > 0 && (
        <div className="moderation-history__list">
          <div className="moderation-history__table-header">
            <span className="moderation-history__col moderation-history__col--time">
              Time
            </span>
            <span className="moderation-history__col moderation-history__col--message">
              Message
            </span>
            <span className="moderation-history__col moderation-history__col--severity">
              Severity
            </span>
            <span className="moderation-history__col moderation-history__col--status">
              Status
            </span>
            <span className="moderation-history__col moderation-history__col--rule">
              Rule
            </span>
            <span className="moderation-history__col moderation-history__col--resolved">
              Resolved By
            </span>
          </div>

          {filteredEvents.map((event) => (
            <div key={event.event_id} className="moderation-history__row-group">
              <div
                className="moderation-history__row"
                onClick={() => toggleExpand(event.event_id)}
              >
                <span className="moderation-history__col moderation-history__col--time">
                  {formatTimestamp(event.created_at)}
                </span>
                <span className="moderation-history__col moderation-history__col--message">
                  {truncate(event.message_content, 80)}
                </span>
                <span className="moderation-history__col moderation-history__col--severity">
                  <SeverityBadge level={event.severity} />
                </span>
                <span className="moderation-history__col moderation-history__col--status">
                  <span
                    className={`moderation-history__status-badge ${getStatusClass(
                      event.status
                    )}`}
                  >
                    {event.status ? event.status.replace(/_/g, " ") : "--"}
                  </span>
                </span>
                <span className="moderation-history__col moderation-history__col--rule">
                  <RuleMatchChip rule={event.matched_rule} />
                </span>
                <span className="moderation-history__col moderation-history__col--resolved">
                  {event.resolved_by || "--"}
                </span>
              </div>

              {expandedId === event.event_id && (
                <div className="moderation-history__expanded">
                  <div className="moderation-history__detail-row">
                    <span className="moderation-history__detail-label">
                      Event ID:
                    </span>
                    <span>{event.event_id}</span>
                  </div>
                  <div className="moderation-history__detail-row">
                    <span className="moderation-history__detail-label">
                      Full Message:
                    </span>
                    <span>{event.message_content}</span>
                  </div>
                  <div className="moderation-history__detail-row">
                    <span className="moderation-history__detail-label">
                      Violation Type:
                    </span>
                    <span>{event.violation_type || "--"}</span>
                  </div>
                  <div className="moderation-history__detail-row">
                    <span className="moderation-history__detail-label">
                      Explanation:
                    </span>
                    <span>{event.explanation || "--"}</span>
                  </div>
                  <div className="moderation-history__detail-row">
                    <span className="moderation-history__detail-label">
                      Suggested Action:
                    </span>
                    <span>
                      {event.suggested_action
                        ? event.suggested_action.replace(/_/g, " ")
                        : "--"}
                    </span>
                  </div>
                  <div className="moderation-history__detail-row">
                    <span className="moderation-history__detail-label">
                      Source:
                    </span>
                    <span>{event.source || "--"}</span>
                  </div>
                  <div className="moderation-history__detail-row">
                    <span className="moderation-history__detail-label">
                      Resolved At:
                    </span>
                    <span>{formatTimestamp(event.resolved_at)}</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
