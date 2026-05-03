import "./RuleMatchChip.css";

export default function RuleMatchChip({ rule, violationType }) {
  if (!rule) return null;
  // Relaxed matched_rule semantics: benign no_violation events may still cite
  // a relevant rule informationally (e.g. "is talking about Medal of Honor
  // allowed?" -> Rule 6). Suppress the chip on no_violation events so users
  // don't read "rule matched" as "you broke a rule" \u2014 the rule still appears
  // in /draft output_text where it's framed as policy guidance.
  if (violationType === "no_violation") return null;

  return <span className="rule-match-chip">{"\u00A7 "}{rule}</span>;
}
