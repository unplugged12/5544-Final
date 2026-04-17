import { motion } from "motion/react";
import "./Sidebar.css";

const TABS = [
  { key: "knowledge", label: "Knowledge Base", icon: "\uD83D\uDCDA" },
  { key: "faq", label: "Ask FAQ", icon: "\u2753" },
  { key: "summarize", label: "Summarize", icon: "\uD83D\uDCDD" },
  { key: "draft", label: "Mod Draft", icon: "\u270F\uFE0F" },
  { key: "review", label: "Review Queue", icon: "\uD83D\uDCCB" },
  { key: "history", label: "History", icon: "\uD83D\uDD70\uFE0F" },
  { key: "settings", label: "Settings", icon: "\u2699\uFE0F" },
];

export default function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside className="sidebar">
      <nav className="sidebar__nav">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              className={`sidebar__tab ${isActive ? "sidebar__tab--active" : ""}`}
              onClick={() => onTabChange(tab.key)}
              aria-current={isActive ? "page" : undefined}
            >
              {isActive && (
                <motion.span
                  layoutId="sidebar-active-pill"
                  className="sidebar__pill"
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                  aria-hidden="true"
                />
              )}
              <span className="sidebar__tab-icon" aria-hidden="true">
                {tab.icon}
              </span>
              <span className="sidebar__tab-label">{tab.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
