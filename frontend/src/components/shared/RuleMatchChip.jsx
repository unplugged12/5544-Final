import "./RuleMatchChip.css";

export default function RuleMatchChip({ rule }) {
  if (!rule) return null;

  return <span className="rule-match-chip">{"\u00A7 "}{rule}</span>;
}
