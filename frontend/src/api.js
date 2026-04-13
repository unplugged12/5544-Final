const BASE_URL = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const status = res.status;
    if (status === 422) {
      throw new Error("Invalid input. Please check your request.");
    } else if (status === 404) {
      throw new Error("Item not found.");
    } else if (status === 500) {
      throw new Error("Server error. Please try again.");
    } else {
      throw new Error("Something went wrong. Please try again.");
    }
  }

  return res.json();
}

export function healthCheck() {
  return request("/api/health");
}

export function getSources(sourceType) {
  const params = sourceType ? `?source_type=${encodeURIComponent(sourceType)}` : "";
  return request(`/api/sources${params}`);
}

export function askFaq(question) {
  return request("/api/faq/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function summarize(text) {
  return request("/api/announcements/summarize", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function draftResponse(situation) {
  return request("/api/moderation/draft", {
    method: "POST",
    body: JSON.stringify({ situation }),
  });
}

export function analyzeMessage(messageContent) {
  return request("/api/moderation/analyze", {
    method: "POST",
    body: JSON.stringify({ message_content: messageContent, source: "dashboard" }),
  });
}

export function approveEvent(eventId) {
  return request(`/api/moderation/approve/${encodeURIComponent(eventId)}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function rejectEvent(eventId) {
  return request(`/api/moderation/reject/${encodeURIComponent(eventId)}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getDemoMode() {
  return request("/api/settings/demo-mode");
}

export function setDemoMode(enabled) {
  return request("/api/settings/demo-mode", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

export function getHistory(limit = 50, offset = 0, status) {
  let url = `/api/history?limit=${limit}&offset=${offset}`;
  if (status) {
    url += `&status=${encodeURIComponent(status)}`;
  }
  return request(url);
}
