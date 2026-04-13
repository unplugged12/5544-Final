import "./SeverityBadge.css";

const SEVERITY_COLORS = {
  low: "severity-low",
  medium: "severity-medium",
  high: "severity-high",
  critical: "severity-critical",
};

export default function SeverityBadge({ level }) {
  if (!level) return null;

  const className = SEVERITY_COLORS[level.toLowerCase()] || "severity-low";

  return (
    <span className={`severity-badge ${className}`}>
      {level.toUpperCase()}
    </span>
  );
}
