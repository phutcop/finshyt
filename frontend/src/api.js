const apiBase = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
const sessionKey = "finshyt:sessionId";

function sessionId() {
  let value = localStorage.getItem(sessionKey);
  if (!value) {
    value = crypto.randomUUID();
    localStorage.setItem(sessionKey, value);
  }
  return value;
}

export function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set("X-Finshyt-Session", sessionId());
  return fetch(`${apiBase}${path}`, { ...options, headers });
}
