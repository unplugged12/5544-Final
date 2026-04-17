import { useState, useEffect, useCallback } from "react";
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
import { formatEnumValue } from "../utils/formatEnum.js";
import "./ReviewQueue.css";

export default function ReviewQueue() {
  const [pendingEvents, setPendingEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const analyze = useApi(analyzeMessage);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getHistory(200, 0, "pending");
      setPendingEvents(result.events || []);
    } catch (err) {
      setError(err.message || "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  const handleApprove = async (eventId) => {
    setActionLoading(eventId);
    try {
      await approveEvent(eventId);
      await fetchPending();
    } catch (err) {
      setError(err.message || "Failed to approve event");
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (eventId) => {
    setActionLoading(eventId);
    try {
      await rejectEvent(eventId);
      await fetchPending();
    } catch (err) {
      setError(err.message || "Failed to reject event");
    } finally {
      setActionLoading(null);
    }
  };

  const handleAnalyze = (message) => {
    analyze.execute(message);
  };

  return (
    <div className="review-queue">
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
        {analyze.error && (
          <div className="review-queue__error">{analyze.error}</div>
        )}
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

        {error && <div className="review-queue__error">{error}</div>}

        {loading && (
          <div className="review-queue__loading">Loading queue...</div>
        )}

        {!loading && !error && pendingEvents.length === 0 && (
          <div className="review-queue__empty">
            No pending events in the queue.
          </div>
        )}

        {!loading &&
          pendingEvents.map((event) => {
            const isBusy = actionLoading === event.event_id;
            return (
              <div
                key={event.event_id}
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
                        Processing…
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
                        Processing…
                      </span>
                    ) : (
                      "Reject"
                    )}
                  </button>
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
