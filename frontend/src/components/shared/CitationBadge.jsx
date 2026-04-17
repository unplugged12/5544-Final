import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import "./CitationBadge.css";

export default function CitationBadge({ label, snippet }) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span
      className="citation-badge"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onFocus={() => setShowTooltip(true)}
      onBlur={() => setShowTooltip(false)}
      tabIndex={snippet ? 0 : -1}
    >
      {label}
      <AnimatePresence>
        {showTooltip && snippet && (
          <motion.span
            className="citation-tooltip"
            role="tooltip"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18, ease: [0, 0, 0.2, 1] }}
          >
            {snippet}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}
