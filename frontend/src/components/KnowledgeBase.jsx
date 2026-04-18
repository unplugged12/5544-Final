import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import { getSources } from "../api.js";
import { SkeletonGrid } from "./shared/Skeleton.jsx";
import "./KnowledgeBase.css";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "rule", label: "Rules" },
  { key: "faq", label: "FAQs" },
  { key: "announcement", label: "Announcements" },
  { key: "mod_note", label: "Mod Notes" },
];

const TYPE_LABELS = {
  rule: "Rule",
  faq: "FAQ",
  announcement: "Announcement",
  mod_note: "Mod Note",
};

// Cap animated children so large lists don't feel slow.
const MAX_STAGGERED = 12;

function KbCard({ source, index, expanded, onToggle }) {
  const shouldAnimate = index < MAX_STAGGERED;
  const preview =
    source.content
      ? source.content.length > 150
        ? source.content.substring(0, 150) + "..."
        : source.content
      : "No content preview available.";
  const contentId = `kb-content-${source.source_id}`;

  const CardInner = (
    <button
      type="button"
      className={`kb-card card-glass knowledge-base__card${
        expanded ? " knowledge-base__card--expanded" : ""
      }`}
      onClick={onToggle}
      aria-expanded={expanded}
      aria-controls={contentId}
    >
      <span className="knowledge-base__card-header">
        <span className="knowledge-base__card-title">
          {source.title || source.source_id}
        </span>
        <span
          className={`knowledge-base__type-badge knowledge-base__type-badge--${source.source_type}`}
        >
          {TYPE_LABELS[source.source_type] || source.source_type}
        </span>
      </span>

      {!expanded && (
        <span className="knowledge-base__card-preview">{preview}</span>
      )}

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.span
            key="expanded"
            id={contentId}
            className="knowledge-base__card-full"
            role="region"
            aria-label={`${source.title || source.source_id} content`}
            initial={{ opacity: 0, height: 0 }}
            animate={{
              opacity: 1,
              height: "auto",
              transition: { duration: 0.25, ease: [0.4, 0, 0.2, 1] },
            }}
            exit={{
              opacity: 0,
              height: 0,
              transition: { duration: 0.2, ease: [0.4, 0, 1, 1] },
            }}
          >
            <span className="knowledge-base__card-full-inner">
              {source.content || "No content available."}
            </span>
          </motion.span>
        )}
      </AnimatePresence>

      <span className="knowledge-base__card-foot">
        <span className="knowledge-base__card-id">{source.source_id}</span>
        <span
          className={`knowledge-base__chevron${
            expanded ? " knowledge-base__chevron--open" : ""
          }`}
          aria-hidden="true"
        >
          ▸
        </span>
      </span>
    </button>
  );

  if (!shouldAnimate) {
    return (
      <motion.div className="knowledge-base__card-wrap" layout>
        {CardInner}
      </motion.div>
    );
  }

  return (
    <motion.div
      className="knowledge-base__card-wrap"
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{
        opacity: 1,
        y: 0,
        transition: {
          delay: index * 0.04,
          duration: 0.32,
          ease: [0, 0, 0.2, 1],
        },
      }}
    >
      {CardInner}
    </motion.div>
  );
}

export default function KnowledgeBase() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeFilter, setActiveFilter] = useState("all");
  const [expandedId, setExpandedId] = useState(null);

  const fetchSources = async (filter) => {
    setLoading(true);
    setError(null);
    try {
      const sourceType = filter === "all" ? undefined : filter;
      const result = await getSources(sourceType);
      setSources(result.sources || []);
    } catch (err) {
      setError(err.message || "Failed to load knowledge base");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSources(activeFilter);
    // Collapse any open card when the filter changes (grid reshuffles)
    setExpandedId(null);
  }, [activeFilter]);

  const handleFilterChange = (key) => {
    setActiveFilter(key);
  };

  // Stable ordering so Motion layout animations are smooth
  const orderedSources = useMemo(() => sources, [sources]);

  return (
    <div className="knowledge-base">
      <h2 className="knowledge-base__title">Knowledge Base</h2>
      <p className="knowledge-base__subtitle">
        Browse server rules, FAQs, announcements, and moderator notes.
      </p>

      <div className="knowledge-base__filters" role="tablist" aria-label="Filter by type">
        {FILTERS.map((f) => {
          const isActive = activeFilter === f.key;
          return (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`knowledge-base__filter-btn${
                isActive ? " knowledge-base__filter-btn--active" : ""
              }`}
              onClick={() => handleFilterChange(f.key)}
            >
              {isActive && (
                <motion.span
                  layoutId="kb-filter-active"
                  className="knowledge-base__filter-pill"
                  transition={{ type: "spring", stiffness: 420, damping: 32 }}
                />
              )}
              <span className="knowledge-base__filter-label">{f.label}</span>
            </button>
          );
        })}
      </div>

      {error && <div className="knowledge-base__error">{error}</div>}

      {loading && <SkeletonGrid count={6} />}

      {!loading && !error && sources.length === 0 && (
        <div className="knowledge-base__empty">No sources found.</div>
      )}

      {!loading && !error && sources.length > 0 && (
        <motion.div className="knowledge-base__grid" layout>
          {orderedSources.map((source, index) => (
            <KbCard
              key={source.source_id}
              source={source}
              index={index}
              expanded={expandedId === source.source_id}
              onToggle={() =>
                setExpandedId((cur) =>
                  cur === source.source_id ? null : source.source_id
                )
              }
            />
          ))}
        </motion.div>
      )}
    </div>
  );
}
