// localStorage that cannot take the app down with it.
//
// Every accessor here throws rather than returning null in a private
// window, when site data is blocked, or when the quota is full -- and
// `localStorage` itself throws on mere property access in some embedded
// webviews, which matters here because this app is meant to ship as a TWA.
//
// The interview flow already wrapped each of its own calls. Auth did not,
// and the consequence was worse than a lost preference: login() awaited
// the API, received a real token, and then threw inside persist() before
// any state was set -- so the user saw "login failed" while actually
// holding valid credentials, and retrying just issued another token.
//
// Storage is a convenience everywhere it is used here. Losing it should
// cost a session that ends when the tab closes, never a broken flow.

export function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    // Unavailable, or corrupt JSON. Both mean "nothing to restore".
    return null;
  }
}

/** Returns whether it stuck, for the rare caller that wants to know. */
export function writeJson(key: string, value: unknown): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function remove(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* Nothing to do -- it is already not readable. */
  }
}

export function readString(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeString(key: string, value: string): boolean {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}
