import { useState } from "react";
import "./CitationBadge.css";

export default function CitationBadge({ label, snippet }) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span
      className="citation-badge"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {label}
      {showTooltip && snippet && (
        <span className="citation-tooltip">{snippet}</span>
      )}
    </span>
  );
}
