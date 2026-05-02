import { useState, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  getHistory,
  analyzeMessage,
  approveEvent,
  rejectEvent,
} from "../api.js";
import useApi from "../hooks/useApi.js";
import useCountUp from "../hooks/useCountUp.js";
import PromptInput from "./shared/PromptInput.jsx";
import ResponsePanel from "./shared/ResponsePanel.jsx";
import SeverityBadge from "./shared/SeverityBadge.jsx";
import RuleMatchChip from "./shared/RuleMatchChip.jsx";
import { useToasts, ToastContainer } from "./shared/Toast.jsx";
import { formatEnumValue } from "../utils/formatEnum.js";
import "./ReviewQueue.css";

// Brief checkmark animation shown over a card right before it fades out.
// Stroke-dasharray draw-in over ~320ms. Pure SVG + CSS, no extra deps.
function ConfirmOverlay({ variant }) {
  const isApprove = variant === "approved";
  const label = isApprove ? "Approved" : "Rejected";
  return (
    <motion.div
      className={`review-queue__confirm review-queue__confirm--${variant}`}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease: [0, 0, 0.2, 1] }}
      aria-hidden="true"
    >
      <svg
        className="review-queue__confirm-icon"
        viewBox="0 0 48 48"
        width="48"
        height="48"
      >
        <circle
          className="review-queue__confirm-circle"
          cx="24"
          cy="24"
          r="21"
          fill="none"
          strokeWidth="2.5"
        />
        {isApprove ? (
          <path
            className="review-queue__confirm-check"
            d="M14 25 L21 32 L34 17"
            fill="none"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : (
          <g className="review-queue__confirm-check">
            <path
              d="M17 17 L31 31"
              fill="none"
              strokeWidth="3.5"
              strokeLinecap="round"
            />
            <path
              d="M31 17 L17 31"
              fill="none"
              strokeWidth="3.5"
              strokeLinecap="round"
            />
          </g>
        )}
      </svg>
      <span className="review-queue__confirm-label">{label}</span>
    </motion.div>
  );
}

export default function ReviewQueue() {
  const [pendingEvents, setPendingEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  // Map of eventId -> 'approved' | 'rejected' for the brief celebration overlay.
  const [confirmedMap, setConfirmedMap] = useState({});
  const { toasts, push, dismiss } = useToasts();

  const analyze = useApi(analyzeMessage);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getHistory(200, 0, "pending");
      setPendingEvents(result.events || []);
    } catch (err) {
      const msg = err.message || "Failed to load review queue";
      setError(msg);
      push({ kind: "error", message: msg });
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  // Surface analyze API errors as toasts too (replaces inline error text).
  useEffect(() => {
    if (analyze.error) {
      push({ kind: "error", message: analyze.error });
    }
  }, [analyze.error, push]);

  // Count-up for pending count (animates on mount only; subsequent changes snap).
  const displayedPending = useCountUp(pendingEvents.length);

  const runAction = async (eventId, variant, apiFn) => {
    setActionLoading(eventId);
    try {
      await apiFn(eventId);
      push({
        kind: "success",
        message: variant === "approved" ? "Event approved." : "Event rejected.",
      });
      // Show the celebration overlay, let exit animation play, then refresh.
      setConfirmedMap((m) => ({ ...m, [eventId]: variant }));
      // ~600ms is enough for checkmark draw + fade; matches exit timing below.
      await new Promise((resolve) => setTimeout(resolve, 620));
      await fetchPending();
    } catch (err) {
      const msg =
        err.message ||
        `Failed to ${variant === "approved" ? "approve" : "reject"} event`;
      setError(msg);
      push({ kind: "error", message: msg });
    } finally {
      setActionLoading(null);
      // Always clear the celebration flag — otherwise a throw after we set it
      // leaves the card stuck with disabled action buttons (isConfirming=true).
      setConfirmedMap((m) => {
        if (!(eventId in m)) return m;
        const next = { ...m };
        delete next[eventId];
        return next;
      });
    }
  };

  const handleApprove = (eventId) => runAction(eventId, "approved", approveEvent);
  const handleReject = (eventId) => runAction(eventId, "rejected", rejectEvent);

  const handleAnalyze = (message) => {
    analyze.execute(message);
  };

  return (
    <div className="review-queue">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
      <div className="review-queue__header">
        <div>
          <h2 className="sr-only">Review Queue</h2>
        </div>
        <button
          className="review-queue__refresh-btn"
          onClick={fetchPending}
          disabled={loading}
        >
          Refresh
        </button>
      </div>

      <div className="review-queue__analyze-section">
        <h3 className="review-queue__section-title">Analyze a Message</h3>
        <PromptInput
          placeholder="Paste a message to analyze for rule violations..."
          buttonLabel="Analyze"
          onSubmit={handleAnalyze}
          loading={analyze.loading}
        />
        {analyze.data && (
          <div className="review-queue__analyze-result">
            <ResponsePanel
              response={{
                output_text: analyze.data.explanation,
                severity: analyze.data.severity,
                suggested_action: analyze.data.suggested_action,
                matched_rule: analyze.data.matched_rule,
                violation_type: analyze.data.violation_type,
                citations: [],
                confidence_note: null,
              }}
            />
          </div>
        )}
      </div>

      <div className="review-queue__pending-section">
        <h3 className="review-queue__section-title">
          Pending Events{" "}
          <span className="review-queue__count-num">
            ({displayedPending})
          </span>
        </h3>

        {/* Toast notifies on failure but auto-dismisses after 5s. Persist an
            inline banner so the pane isn't blank once the toast is gone
            (empty/list views below are gated on !error). */}
        {error && <div className="review-queue__error">{error}</div>}

        {loading && <ReviewQueueSkeleton />}

        {!loading && !error && pendingEvents.length === 0 && (
          <div className="review-queue__empty">
            No pending events in the queue.
          </div>
        )}

        {/* AnimatePresence must stay mounted across loading toggles, otherwise
            the card exit transitions configured below never get to play when
            approve/reject triggers a refetch (setLoading(true) would unmount
            the whole tree instantly). */}
        <AnimatePresence initial={false}>
          {pendingEvents.map((event) => {
            const isBusy = actionLoading === event.event_id;
            const confirmedVariant = confirmedMap[event.event_id];
            const isConfirming = Boolean(confirmedVariant);
            return (
              <motion.div
                key={event.event_id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{
                  opacity: 0,
                  y: -6,
                  scale: 0.98,
                  transition: { duration: 0.24, ease: [0.4, 0, 1, 1] },
                }}
                transition={{ duration: 0.25, ease: [0, 0, 0.2, 1] }}
                className={`review-queue__card${
                  isBusy ? " review-queue__card--busy" : ""
                }${isConfirming ? " review-queue__card--confirming" : ""}`}
                aria-busy={isBusy}
              >
                <div className="review-queue__card-top">
                  <div className="review-queue__card-badges">
                    <SeverityBadge level={event.severity} />
                    <RuleMatchChip
                      rule={event.matched_rule}
                      violationType={event.violation_type}
                    />
                  </div>
                  {event.suggested_action && (
                    <span className="review-queue__suggested-action">
                      Suggested: {formatEnumValue(event.suggested_action)}
                    </span>
                  )}
                </div>

                <div className="review-queue__card-message">
                  {event.message_content}
                </div>

                {event.explanation && (
                  <p className="review-queue__card-explanation">
                    {event.explanation}
                  </p>
                )}

                <div className="review-queue__card-actions">
                  <button
                    className="review-queue__approve-btn"
                    onClick={() => handleApprove(event.event_id)}
                    disabled={isBusy || isConfirming}
                  >
                    {isBusy && !isConfirming ? (
                      <span className="review-queue__btn-busy">
                        <span
                          className="review-queue__spinner"
                          aria-hidden="true"
                        />
                        Processing…
                      </span>
                    ) : (
                      "Approve"
                    )}
                  </button>
                  <button
                    className="review-queue__reject-btn"
                    onClick={() => handleReject(event.event_id)}
                    disabled={isBusy || isConfirming}
                  >
                    {isBusy && !isConfirming ? (
                      <span className="review-queue__btn-busy">
                        <span
                          className="review-queue__spinner"
                          aria-hidden="true"
                        />
                        Processing…
                      </span>
                    ) : (
                      "Reject"
                    )}
                  </button>
                </div>

                <AnimatePresence>
                  {isConfirming && (
                    <ConfirmOverlay variant={confirmedVariant} />
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}

function ReviewQueueSkeleton() {
  return (
    <div className="review-queue__skeleton" aria-hidden="true">
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="review-queue__card review-queue__card--skeleton">
          <div className="review-queue__card-top">
            <span className="skeleton" style={{ width: 80, height: 18, borderRadius: 12 }} />
            <span className="skeleton" style={{ width: 120, height: 14 }} />
          </div>
          <span
            className="skeleton"
            style={{ width: "100%", height: 48, borderRadius: 6, marginBottom: 8 }}
          />
          <span className="skeleton" style={{ width: "75%", height: 12, marginBottom: 12 }} />
          <div className="review-queue__card-actions">
            <span className="skeleton" style={{ width: 90, height: 32, borderRadius: 6 }} />
            <span className="skeleton" style={{ width: 90, height: 32, borderRadius: 6 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
