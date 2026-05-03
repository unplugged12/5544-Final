import SeverityBadge from "./SeverityBadge.jsx";
import RuleMatchChip from "./RuleMatchChip.jsx";
import CitationBadge from "./CitationBadge.jsx";
import { formatEnumValue } from "../../utils/formatEnum.js";
import "./ResponsePanel.css";

export default function ResponsePanel({ response }) {
  if (!response) return null;

  const {
    output_text,
    severity,
    suggested_action,
    matched_rule,
    violation_type,
    citations,
    confidence_note,
  } = response;

  return (
    <div className="response-panel">
      <div className="response-panel__body">
        <pre className="response-panel__text">{output_text}</pre>
      </div>

      <div className="response-panel__meta">
        {severity && (
          <div className="response-panel__meta-row">
            <span className="response-panel__meta-label">Severity:</span>
            <SeverityBadge level={severity} />
          </div>
        )}

        {suggested_action && (
          <div className="response-panel__meta-row">
            <span className="response-panel__meta-label">Suggested Action:</span>
            <span className="response-panel__action">
              {formatEnumValue(suggested_action)}
            </span>
          </div>
        )}

        {matched_rule && violation_type !== "no_violation" && (
          <div className="response-panel__meta-row">
            <span className="response-panel__meta-label">Rule:</span>
            <RuleMatchChip rule={matched_rule} violationType={violation_type} />
          </div>
        )}
      </div>

      {citations && citations.length > 0 && (
        <div className="response-panel__citations">
          <span className="response-panel__citations-label">Sources:</span>
          <div className="response-panel__citations-list">
            {citations.map((c, i) => (
              <CitationBadge
                key={c.source_id || i}
                label={c.citation_label}
                snippet={c.snippet}
              />
            ))}
          </div>
        </div>
      )}

      {confidence_note && (
        <p className="response-panel__confidence">{confidence_note}</p>
      )}
    </div>
  );
}
