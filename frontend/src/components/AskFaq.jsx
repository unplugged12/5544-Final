import { useEffect } from "react";
import { askFaq } from "../api.js";
import useApi from "../hooks/useApi.js";
import PromptInput from "./shared/PromptInput.jsx";
import ResponsePanel from "./shared/ResponsePanel.jsx";
import { useToasts, ToastContainer } from "./shared/Toast.jsx";
import "./AskFaq.css";

export default function AskFaq() {
  const { data, loading, error, execute } = useApi(askFaq);
  const { toasts, push, dismiss } = useToasts();

  useEffect(() => {
    if (error) push({ kind: "error", message: error });
  }, [error, push]);

  const handleSubmit = (question) => {
    execute(question);
  };

  return (
    <div className="ask-faq">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
      

      <PromptInput
        placeholder="Ask a question about server rules, policies, or FAQs..."
        buttonLabel="Ask"
        onSubmit={handleSubmit}
        loading={loading}
      />

      <ResponsePanel response={data} />
    </div>
  );
}
