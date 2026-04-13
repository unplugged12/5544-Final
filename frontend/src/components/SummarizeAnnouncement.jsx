import { summarize } from "../api.js";
import useApi from "../hooks/useApi.js";
import PromptInput from "./shared/PromptInput.jsx";
import ResponsePanel from "./shared/ResponsePanel.jsx";
import "./SummarizeAnnouncement.css";

export default function SummarizeAnnouncement() {
  const { data, loading, error, execute } = useApi(summarize);

  const handleSubmit = (text) => {
    execute(text);
  };

  return (
    <div className="summarize-announcement">
      <h2 className="summarize-announcement__title">Summarize Announcement</h2>
      <p className="summarize-announcement__subtitle">
        Paste an announcement and get a concise summary with key points.
      </p>

      <PromptInput
        placeholder="Paste the announcement text here..."
        buttonLabel="Summarize"
        onSubmit={handleSubmit}
        loading={loading}
        rows={6}
      />

      {error && <div className="summarize-announcement__error">{error}</div>}

      <ResponsePanel response={data} />
    </div>
  );
}
