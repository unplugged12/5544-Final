import { useEffect, useState } from "react";
import { draftResponse } from "../api.js";
import useApi from "../hooks/useApi.js";
import PromptInput from "./shared/PromptInput.jsx";
import ResponsePanel from "./shared/ResponsePanel.jsx";
import { useToasts, ToastContainer } from "./shared/Toast.jsx";
import "./ModeratorDraft.css";

export default function ModeratorDraft() {
  const { data, loading, error, execute } = useApi(draftResponse);
  const [copied, setCopied] = useState(false);
  const { toasts, push, dismiss } = useToasts();

  useEffect(() => {
    if (error) push({ kind: "error", message: error });
  }, [error, push]);

  const handleSubmit = (situation) => {
    setCopied(false);
    execute(situation);
  };

  const handleCopy = async () => {
    if (!data?.output_text) return;
    try {
      await navigator.clipboard.writeText(data.output_text);
      setCopied(true);
      push({ kind: "success", message: "Copied to clipboard." });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = data.output_text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      push({ kind: "success", message: "Copied to clipboard." });
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="moderator-draft">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
      <h2 className="moderator-draft__title">Moderator Draft</h2>
      <p className="moderator-draft__subtitle">
        Describe a situation and get a drafted moderation response.
      </p>

      <PromptInput
        placeholder="Describe the moderation situation or paste the user's message..."
        buttonLabel="Draft Response"
        onSubmit={handleSubmit}
        loading={loading}
      />

      {data && (
        <div className="moderator-draft__result">
          <div className="moderator-draft__copy-bar">
            <button
              className="moderator-draft__copy-btn"
              onClick={handleCopy}
            >
              {copied ? "Copied!" : "Copy to Clipboard"}
            </button>
          </div>
          <ResponsePanel response={data} />
        </div>
      )}
    </div>
  );
}
