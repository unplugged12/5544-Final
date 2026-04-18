import { useState, useEffect, useCallback } from "react";
import { motion } from "motion/react";
import {
  getHistory,
  analyzeMessage,
  approveEvent,
  rejectEvent,
} from "../api.js";
import useApi from "../hooks/useApi.js";
import PromptInput from "./shared/PromptInput.jsx";
import ResponsePanel from "./shared/ResponsePanel.jsx";
import SeverityBadge from "./shared/SeverityBadge.jsx";
import RuleMatchChip from "./shared/RuleMatchChip.jsx";
import { useToasts, ToastContainer } from "./shared/Toast.jsx";
import { formatEnumValue } from "../utils/formatEnum.js";
import "./ReviewQueue.css";

// Cap animated cards so large queues render instantly past the fold.
const MAX_STAGGERED = 12;

export default function ReviewQueue() {
  const [pendingEvents, setPendingEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
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

  const handleApprove = async (eventId) => {
    setActionLoading(eventId);
    try {
      await approveEvent(eventId);
      push({ kind: "success", message: "Event approved." });
      await fetchPending();
    } catch (err) {
      const msg = err.message || "Failed to approve event";
      setError(msg);
      push({ kind: "error", message: msg });
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (eventId) => {
    setActionLoading(eventId);
    try {
      await rejectEvent(eventId);
      push({ kind: "success", message: "Event rejected." });
      await fetchPending();
    } catch (err) {
      const msg = err.message || "Failed to reject event";
      setError(msg);
      push({ kind: "error", message: msg });
    } finally {
      setActionLoading(null);
    }
  };

  const handleAnalyze = (message) => {
    analyze.execute(message);
  };

  return (
    <div className="review-queue">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
      <div className="review-queue__header">
        <div>
          <h2 className="review-queue__title">Review Queue</h2>
          <p className="review-queue__subtitle">
            Analyze messages and review pending moderation events.
          </p>
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
                citations: [],
                confidence_note: null,
              }}
            />
          </div>
        )}
      </div>

      <div className="review-queue__pending-section">
        <h3 className="review-queue__section-title">
          Pending Events ({pendingEvents.length})
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

        {!loading &&
          pendingEvents.map((event, index) => {
            const isBusy = actionLoading === event.event_id;
            const animated = index < MAX_STAGGERED;
            return (
              <motion.div
                key={event.event_id}
                initial={animated ? { opacity: 0, y: 10 } : false}
                animate={
                  animated
                    ? {
                        opacity: 1,
                        y: 0,
                        transition: {
                          delay: index * 0.04,
                          duration: 0.3,
                          ease: [0, 0, 0.2, 1],
                        },
                      }
                    : undefined
                }
                className={`review-queue__card${
                  isBusy ? " review-queue__card--busy" : ""
                }`}
                aria-busy={isBusy}
              >
                <div className="review-queue__card-top">
                  <div className="review-queue__card-badges">
                    <SeverityBadge level={event.severity} />
                    <RuleMatchChip rule={event.matched_rule} />
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
                    disabled={isBusy}
                  >
                    {isBusy ? (
                      <span className="review-queue__btn-busy">
                        <span
                          className="review-queue__spinner"
                          aria-hidden="true"
                        />
                        Processing&hellip;
                      </span>
                    ) : (
                      "Approve"
                    )}
                  </button>
                  <button
                    className="review-queue__reject-btn"
                    onClick={() => handleReject(event.event_id)}
                    disabled={isBusy}
                  >
                    {isBusy ? (
                      <span className="review-queue__btn-busy">
                        <span
                          className="review-queue__spinner"
                          aria-hidden="true"
                        />
                        Processing&hellip;
                      </span>
                    ) : (
                      "Reject"
                    )}
                  </button>
                </div>
              </motion.div>
            );
          })}
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
