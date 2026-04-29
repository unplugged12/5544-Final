import { useState, useEffect } from "react";
import { motion, AnimatePresence, MotionConfig } from "motion/react";
import { healthCheck, getDemoMode, setDemoMode } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import StatusIndicator from "./components/shared/StatusIndicator.jsx";
import KnowledgeBase from "./components/KnowledgeBase.jsx";
import AskFaq from "./components/AskFaq.jsx";
import SummarizeAnnouncement from "./components/SummarizeAnnouncement.jsx";
import ModeratorDraft from "./components/ModeratorDraft.jsx";
import ReviewQueue from "./components/ReviewQueue.jsx";
import ModerationHistory from "./components/ModerationHistory.jsx";
import Settings from "./components/Settings.jsx";
import "./App.css";
import BattleBanner from "./components/shared/BattleBanner.jsx";

function renderTab(activeTab) {
  switch (activeTab) {
    case "knowledge":
      return <KnowledgeBase />;
    case "faq":
      return <AskFaq />;
    case "summarize":
      return <SummarizeAnnouncement />;
    case "draft":
      return <ModeratorDraft />;
    case "review":
      return <ReviewQueue />;
    case "history":
      return <ModerationHistory />;
    case "settings":
      return <Settings />;
    default:
      return <KnowledgeBase />;
  }
}

function ConnectingSplash() {
  return (
    <div className="app app--splash">
      <main className="app__splash">
        <motion.div
          className="splash"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0, 0, 0.2, 1] }}
        >
          <div className="splash__logo" aria-hidden="true">
            <span className="splash__logo-text">ModBot</span>
          </div>
          <div className="splash__spinner" aria-hidden="true">
            <span />
          </div>
          <p className="splash__message">Connecting to backend&hellip;</p>
        </motion.div>
      </main>
    </div>
  );
}

const BANNER_LABELS = {
  knowledge: "Knowledge Base",
  faq: "Ask FAQ",
  summarize: "Summarize Announcement",
  draft: "Moderator Draft",
  review: "Review Queue",
  history: "Moderation History",
  settings: "Settings",
};

const ACTIVE_TAB_STORAGE_KEY = "esports-mod-copilot-active-tab";

export default function App() {
  const [activeTab, setActiveTab] = useState(() => {
  try {
    return localStorage.getItem(ACTIVE_TAB_STORAGE_KEY) || "knowledge";
  } catch {
    return "knowledge";
  }
});
  const [demoMode, setDemoModeState] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("connecting"); // "connecting" | "connected" | "failed"

  const connect = () => {
    setConnectionStatus("connecting");
    healthCheck()
      .then(() => {
        setConnectionStatus("connected");
        return getDemoMode();
      })
      .then((res) => setDemoModeState(res.demo_mode))
      .catch(() => {
        setConnectionStatus("failed");
      });
  };

  useEffect(() => {
    connect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
  try {
    localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeTab);
  } catch {
    // ignore storage errors
  }
}, [activeTab]);

  const handleToggleDemo = async () => {
    const newMode = !demoMode;
    try {
      const res = await setDemoMode(newMode);
      setDemoModeState(res.demo_mode);
    } catch {
      // If API fails, toggle locally anyway for UX
      setDemoModeState(newMode);
    }
  };

  return (
    <MotionConfig reducedMotion="user">
      {connectionStatus === "connecting" && <ConnectingSplash />}

      {connectionStatus === "failed" && (
        <div className="app">
          <main
            className="app__content"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: "16px",
            }}
          >
            <p>Backend unavailable &mdash; check that the server is running.</p>
            <button className="app__retry-btn" onClick={connect}>
              Retry
            </button>
          </main>
        </div>
      )}

      {connectionStatus === "connected" && (
        <div className="app">
          <header className="app__header">
            <div className="app__header-left">
              <h1 className="app__title">Esports Mod Copilot</h1>
            </div>
            <div className="app__header-right">
              <StatusIndicator demoMode={demoMode} onToggle={handleToggleDemo} />
            </div>
          </header>

          <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

          <main className="app__content">
            <BattleBanner pageName={BANNER_LABELS[activeTab] ?? "Knowledge Base"} />

            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                className="app__tab-panel"
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
              >
                {renderTab(activeTab)}
              </motion.div>
            </AnimatePresence>
          </main>

          <footer className="app__footer">
            <span>Esports Mod Copilot &mdash; POC</span>
          </footer>
        </div>
      )}
    </MotionConfig>
  );
}
