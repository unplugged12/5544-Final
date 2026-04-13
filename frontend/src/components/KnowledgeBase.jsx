import { useState, useEffect } from "react";
import { getSources } from "../api.js";
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

export default function KnowledgeBase() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeFilter, setActiveFilter] = useState("all");

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
  }, [activeFilter]);

  const handleFilterChange = (key) => {
    setActiveFilter(key);
  };

  return (
    <div className="knowledge-base">
      <h2 className="knowledge-base__title">Knowledge Base</h2>
      <p className="knowledge-base__subtitle">
        Browse server rules, FAQs, announcements, and moderator notes.
      </p>

      <div className="knowledge-base__filters">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`knowledge-base__filter-btn ${
              activeFilter === f.key ? "knowledge-base__filter-btn--active" : ""
            }`}
            onClick={() => handleFilterChange(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <div className="knowledge-base__error">{error}</div>}

      {loading && <div className="knowledge-base__loading">Loading sources...</div>}

      {!loading && !error && sources.length === 0 && (
        <div className="knowledge-base__empty">No sources found.</div>
      )}

      {!loading && !error && sources.length > 0 && (
        <div className="knowledge-base__grid">
          {sources.map((source) => (
            <div key={source.source_id} className="knowledge-base__card">
              <div className="knowledge-base__card-header">
                <span className="knowledge-base__card-title">
                  {source.title || source.source_id}
                </span>
                <span
                  className={`knowledge-base__type-badge knowledge-base__type-badge--${source.source_type}`}
                >
                  {TYPE_LABELS[source.source_type] || source.source_type}
                </span>
              </div>
              <p className="knowledge-base__card-preview">
                {source.content
                  ? source.content.length > 150
                    ? source.content.substring(0, 150) + "..."
                    : source.content
                  : "No content preview available."}
              </p>
              <span className="knowledge-base__card-id">{source.source_id}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
