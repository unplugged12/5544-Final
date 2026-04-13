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
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`sidebar__tab ${
              activeTab === tab.key ? "sidebar__tab--active" : ""
            }`}
            onClick={() => onTabChange(tab.key)}
          >
            <span className="sidebar__tab-icon">{tab.icon}</span>
            <span className="sidebar__tab-label">{tab.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
