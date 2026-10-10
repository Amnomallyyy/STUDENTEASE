// One profile per browser tab. A random id lives in sessionStorage and goes to the backend as
// X-Session-Id on every request, so two people (or two tabs) never see each other's CV. Closing the tab
// forgets it; "Delete my data" rotates it.
const KEY = "careerlens-sid";

function randomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID().replace(/-/g, "");
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
}

export function sessionId(): string {
  try {
    const existing = window.sessionStorage.getItem(KEY);
    if (existing) return existing;
    const fresh = randomId();
    window.sessionStorage.setItem(KEY, fresh);
    return fresh;
  } catch {
    return "default";
  }
}

/** A new id, so the server slot used so far is abandoned (used by "Delete my data"). */
export function rotateSessionId(): string {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
  return sessionId();
}

/** The request options with the session header merged in. */
export function withSession(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers ?? {});
  headers.set("X-Session-Id", sessionId());
  return { ...init, headers };
}
