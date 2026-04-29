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
    <motion.button
      type="button"
      layout
      transition={{ layout: { type: "spring", stiffness: 260, damping: 28 } }}
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

      <span
        className={`knowledge-base__card-preview${
          expanded ? " knowledge-base__card-preview--expanded" : ""
        }`}
      >
        {preview}
      </span>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.span
            key="expanded"
            id={contentId}
            className="knowledge-base__card-full"
            role="region"
            aria-label={`${source.title || source.source_id} content`}
            initial={{ height: 0, opacity: 0 }}
            animate={{
              height: "auto",
              opacity: 1,
              transition: {
                height: { duration: 0.3, ease: [0.22, 1, 0.36, 1] },
                opacity: { duration: 0.2, delay: 0.06 },
              },
            }}
            exit={{
              height: 0,
              opacity: 0,
              transition: {
                height: { duration: 0.22, ease: [0.4, 0, 1, 1] },
                opacity: { duration: 0.14 },
              },
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
    </motion.button>
  );

  if (!shouldAnimate) {
    return (
      <motion.div
        className="knowledge-base__card-wrap"
        layout
        transition={{ layout: { type: "spring", stiffness: 260, damping: 28 } }}
      >
        {CardInner}
      </motion.div>
    );
  }

  return (
    <motion.div
      className="knowledge-base__card-wrap"
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        layout: { type: "spring", stiffness: 260, damping: 28 },
        opacity: { delay: index * 0.04, duration: 0.32, ease: [0, 0, 0.2, 1] },
        y: { delay: index * 0.04, duration: 0.32, ease: [0, 0, 0.2, 1] },
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
    setExpandedId(null);
  }, [activeFilter]);

  const handleFilterChange = (key) => {
    setActiveFilter(key);
  };

  const orderedSources = useMemo(() => sources, [sources]);

  return (
    <div className="knowledge-base">
      <div
        className="knowledge-base__filters"
        role="group"
        aria-label="Filter by type"
      >
        {FILTERS.map((f) => {
          const isActive = activeFilter === f.key;
          return (
            <button
              key={f.key}
              type="button"
              aria-pressed={isActive}
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
