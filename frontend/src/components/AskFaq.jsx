import { askFaq } from "../api.js";
import useApi from "../hooks/useApi.js";
import PromptInput from "./shared/PromptInput.jsx";
import ResponsePanel from "./shared/ResponsePanel.jsx";
import "./AskFaq.css";

export default function AskFaq() {
  const { data, loading, error, execute } = useApi(askFaq);

  const handleSubmit = (question) => {
    execute(question);
  };

  return (
    <div className="ask-faq">
      <h2 className="ask-faq__title">Ask FAQ</h2>
      <p className="ask-faq__subtitle">
        Ask a question and get answers sourced from the knowledge base.
      </p>

      <PromptInput
        placeholder="Ask a question about server rules, policies, or FAQs..."
        buttonLabel="Ask"
        onSubmit={handleSubmit}
        loading={loading}
      />

      {error && <div className="ask-faq__error">{error}</div>}

      <ResponsePanel response={data} />
    </div>
  );
}
