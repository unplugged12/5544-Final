import { useState, useEffect, useCallback } from "react";
import { getHistory, undoDisciplineForEvent } from "../api.js";
import useCountUp from "../hooks/useCountUp.js";
import SeverityBadge from "./shared/SeverityBadge.jsx";
import RuleMatchChip from "./shared/RuleMatchChip.jsx";
import { SkeletonList } from "./shared/Skeleton.jsx";
import { useToasts, ToastContainer } from "./shared/Toast.jsx";
import { formatEnumValue } from "../utils/formatEnum.js";
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
  const [undoing, setUndoing] = useState(null);
  const [undoMsg, setUndoMsg] = useState({});
  const { toasts, push, dismiss } = useToasts();

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getHistory(200, 0);
      setEvents(result.events || []);
      setTotal(result.total || 0);
    } catch (err) {
      const msg = err.message || "Failed to load history";
      setError(msg);
      push({ kind: "error", message: msg });
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Count-up for total (on mount only; subsequent changes snap)
  const displayedTotal = useCountUp(total);

  const filteredEvents =
    activeFilter === "all"
      ? events
      : events.filter((e) => e.status === activeFilter);

  const toggleExpand = (eventId) => {
    setExpandedId(expandedId === eventId ? null : eventId);
  };

  const handleUndo = async (eventId) => {
    setUndoing(eventId);
    setUndoMsg((m) => ({ ...m, [eventId]: "" }));
    try {
      const res = await undoDisciplineForEvent(eventId);
      const msg = res.reason
        ? `Undo: ${res.reason}`
        : `Undone (${res.violations_revoked ?? 0} violations revoked, ${res.actions_marked_undone ?? 0} actions marked)`;
      setUndoMsg((m) => ({ ...m, [eventId]: msg }));
      push({ kind: res.reason ? "warning" : "success", message: msg });
      // Refresh to pick up any backend-side state changes
      fetchHistory();
    } catch (err) {
      const msg = err.message || "Undo failed";
      setUndoMsg((m) => ({ ...m, [eventId]: msg }));
      push({ kind: "error", message: msg });
    } finally {
      setUndoing(null);
    }
  };

  return (
    <div className="moderation-history">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
      <div className="moderation-history__header">
        <div>
          <h2 className="moderation-history__title">Moderation History</h2>
          <p className="moderation-history__subtitle">
            Browse past moderation events and their outcomes.
            {total > 0 && (
              <span className="moderation-history__count">
                {" "}(
                <span className="moderation-history__count-num">
                  {displayedTotal}
                </span>{" "}
                total)
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

      {/* Toast notifies on failure but auto-dismisses after 5s. Persist an
          inline banner so the pane isn't a blank mystery once the toast is
          gone (empty/list views below are gated on !error). */}
      {error && <div className="moderation-history__error">{error}</div>}

      {loading && <SkeletonList rows={6} columns={6} />}

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
                    {event.status ? formatEnumValue(event.status) : "--"}
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
                        ? formatEnumValue(event.suggested_action)
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
                  {event.discipline_action && event.discipline_action !== "none" && (
                    <div className="moderation-history__detail-row">
                      <span className="moderation-history__detail-label">
                        Discipline:
                      </span>
                      <span>{formatEnumValue(event.discipline_action)}</span>
                    </div>
                  )}
                  {event.status === "auto_actioned" &&
                    event.discord_user_id &&
                    event.discipline_action &&
                    event.discipline_action !== "none" && (
                      <div className="moderation-history__undo">
                        <button
                          className="moderation-history__undo-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleUndo(event.event_id);
                          }}
                          disabled={undoing === event.event_id}
                        >
                          {undoing === event.event_id ? "Undoing…" : "Undo discipline"}
                        </button>
                        {undoMsg[event.event_id] && (
                          <span className="moderation-history__undo-msg">
                            {undoMsg[event.event_id]}
                          </span>
                        )}
                        <p className="moderation-history__undo-hint">
                          Revokes this user's violation points and marks the kick/ban as undone.
                          Any active Discord ban must be lifted manually in the server.
                        </p>
                      </div>
                    )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
