"use client";

// Auth state lives in localStorage (not just in-memory React state) so a
// page refresh doesn't log the user out -- an actual improvement over the
// Streamlit app, where st.session_state never survives a browser refresh.

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import type { User } from "./types";
import * as api from "./api";

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
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      try {
        const saved: { token: string; user: User } = JSON.parse(raw);
        const freshUser = await api.getMe(saved.token);
        if (cancelled) return;
        setToken(saved.token);
        setUser(freshUser);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
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
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: newToken, user: newUser }));
    setToken(newToken);
    setUser(newUser);
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
    localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setUser(null);
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
