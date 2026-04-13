import { useState } from "react";
import "./PromptInput.css";

export default function PromptInput({
  placeholder,
  buttonLabel,
  onSubmit,
  loading,
  rows = 3,
}) {
  const [value, setValue] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!value.trim() || loading) return;
    onSubmit(value.trim());
    setValue("");
  };

  return (
    <form className="prompt-input" onSubmit={handleSubmit}>
      <textarea
        className="prompt-input__textarea"
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={rows}
        disabled={loading}
      />
      <button
        className="prompt-input__button"
        type="submit"
        disabled={loading || !value.trim()}
      >
        {loading ? "Processing..." : buttonLabel}
      </button>
    </form>
  );
}
