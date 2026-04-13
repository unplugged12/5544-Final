import { useState, useEffect } from "react";
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

export default function App() {
  const [activeTab, setActiveTab] = useState("knowledge");
  const [demoMode, setDemoModeState] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("connecting"); // "connecting" | "connected" | "failed"

  useEffect(() => {
    healthCheck()
      .then(() => {
        setConnectionStatus("connected");
        return getDemoMode();
      })
      .then((res) => setDemoModeState(res.demo_mode))
      .catch(() => {
        setConnectionStatus("failed");
      });
  }, []);

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

  if (connectionStatus === "connecting") {
    return (
      <div className="app">
        <main className="app__content" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p>Connecting to backend...</p>
        </main>
      </div>
    );
  }

  if (connectionStatus === "failed") {
    return (
      <div className="app">
        <main className="app__content" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p>Backend unavailable &mdash; check that the server is running.</p>
        </main>
      </div>
    );
  }

  return (
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

      <main className="app__content">{renderTab(activeTab)}</main>

      <footer className="app__footer">
        <span>Esports Mod Copilot &mdash; POC</span>
      </footer>
    </div>
  );
}
