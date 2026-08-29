"use client";

// Lets a resume picked on one page (Interview Session, Resume Analysis, ATS
// Score, Predicted Questions) be reused on another without re-pasting or
// re-uploading it. Lives in-memory only (a React Context, like auth-context
// keeps its in-memory state before hydrating from localStorage) -- it
// survives client-side navigation between pages in this tab, since Next.js
// App Router doesn't reload the JS runtime on those, but intentionally does
// NOT persist across a hard refresh or a new tab: an uploaded PDF is a File
// object, which can't be serialized into localStorage, and silently
// resurrecting a resume across browser sessions would be more surprising
// than losing it -- session-scoped "remember what I just used" is the goal
// here, not durable storage.

import { createContext, useContext, useState, ReactNode } from "react";

export interface SharedResume {
  method: "paste" | "upload";
  text: string;
  file: File | null;
  savedAt: number;
}

interface ResumeContextValue {
  lastResume: SharedResume | null;
  saveResume: (r: { method: "paste" | "upload"; text: string; file: File | null }) => void;
}

const ResumeContext = createContext<ResumeContextValue | null>(null);

export function ResumeProvider({ children }: { children: ReactNode }) {
  const [lastResume, setLastResume] = useState<SharedResume | null>(null);

  function saveResume(r: { method: "paste" | "upload"; text: string; file: File | null }) {
    const hasContent = r.method === "paste" ? r.text.trim().length > 0 : !!r.file;
    if (!hasContent) return;
    setLastResume({ ...r, savedAt: Date.now() });
  }

  return (
    <ResumeContext.Provider value={{ lastResume, saveResume }}>{children}</ResumeContext.Provider>
  );
}

export function useSharedResume(): ResumeContextValue {
  const ctx = useContext(ResumeContext);
  if (!ctx) throw new Error("useSharedResume must be used within a ResumeProvider");
  return ctx;
}
