"use client";

// Auth state lives in localStorage (not just in-memory React state) so a
// page refresh doesn't log the user out -- an actual improvement over the
// Streamlit app, where st.session_state never survives a browser refresh.

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import type { User } from "./types";
import * as api from "./api";
import * as storage from "./safe-storage";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const STORAGE_KEY = "reflectinterview_auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // On first mount, restore a saved session and confirm the token is still
  // valid against /auth/me rather than trusting a possibly-expired token.
  // Every setState call here happens inside the async restore()/.finally()
  // chain (never synchronously in the effect body itself), which is what
  // react-hooks' set-state-in-effect rule wants -- the effect just kicks
  // off synchronization with two external systems (localStorage, the API)
  // and reacts to their result in a callback.
  useEffect(() => {
    let cancelled = false;

    async function restore() {
      // Was outside the try, so blocked storage threw here and rejected
      // this promise -- .finally still cleared loading, but the rejection
      // went unhandled and surfaced in the console on every load.
      const saved = storage.readJson<{ token: string; user: User }>(STORAGE_KEY);
      if (!saved?.token) return;
      try {
        const freshUser = await api.getMe(saved.token);
        if (cancelled) return;
        setToken(saved.token);
        setUser(freshUser);
      } catch {
        // The token is stale, revoked, or the account was deleted.
        storage.remove(STORAGE_KEY);
      }
    }

    restore().finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  function persist(newToken: string, newUser: User) {
    // State first, storage second, and the write cannot throw.
    //
    // The old order did the opposite with a bare setItem, so a private
    // window or a full quota threw before either setState ran: login()
    // rejected and reported failure even though the API had already
    // issued a valid token. Failing to remember a session across reloads
    // is a small loss; failing the login outright is not.
    setToken(newToken);
    setUser(newUser);
    storage.writeJson(STORAGE_KEY, { token: newToken, user: newUser });
  }

  async function login(email: string, password: string) {
    const result = await api.login(email, password);
    persist(result.access_token, result.user);
  }

  async function signup(email: string, password: string, name?: string) {
    const result = await api.signup(email, password, name);
    persist(result.access_token, result.user);
  }

  function logout() {
    // Clear state first for the same reason: a throwing removeItem must
    // not be able to leave someone logged in after they asked to leave.
    setToken(null);
    setUser(null);
    storage.remove(STORAGE_KEY);
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
