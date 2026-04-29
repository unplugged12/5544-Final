import { useEffect } from "react";
import { summarize } from "../api.js";
import useApi from "../hooks/useApi.js";
import PromptInput from "./shared/PromptInput.jsx";
import ResponsePanel from "./shared/ResponsePanel.jsx";
import { useToasts, ToastContainer } from "./shared/Toast.jsx";
import "./SummarizeAnnouncement.css";

export default function SummarizeAnnouncement() {
  const { data, loading, error, execute } = useApi(summarize);
  const { toasts, push, dismiss } = useToasts();

  useEffect(() => {
    if (error) push({ kind: "error", message: error });
  }, [error, push]);

  const handleSubmit = (text) => {
    execute(text);
  };

  return (
    <div className="summarize-announcement">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
      

      <PromptInput
        placeholder="Paste the announcement text here..."
        buttonLabel="Summarize"
        onSubmit={handleSubmit}
        loading={loading}
        rows={6}
      />

      <ResponsePanel response={data} />
    </div>
  );
}
