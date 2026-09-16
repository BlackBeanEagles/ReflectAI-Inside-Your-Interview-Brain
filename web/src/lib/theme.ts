"use client";

// One source of truth for light/dark.
//
// The theme is read by two components that must never disagree -- the
// header toggle and the command palette, which both show the *opposite*
// theme as their label. Two useState copies would drift the moment either
// one flipped it, so this is a module-level store with subscribers and
// useSyncExternalStore on top, which is what React offers for exactly this
// shape of shared, non-prop state.
//
// Dark is opt-in via a data-theme attribute and deliberately does NOT
// follow prefers-color-scheme: the app used to inherit the OS setting and
// handed people a dark interview room they never asked for.

import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

const THEME_KEY = "reflectinterview_theme";

let current: Theme = "light";
const listeners = new Set<() => void>();

function readStored(): Theme | null {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "dark" || v === "light" ? v : null;
  } catch {
    // A private window throws here rather than returning null.
    return null;
  }
}

/** Sync the store to whatever the inline <head> script already applied, so
 *  the first render matches the DOM instead of flashing back to light. */
function syncFromDocument(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function getSnapshot(): Theme {
  return current;
}

// The server renders the light default. It cannot know the stored choice,
// and guessing would produce a hydration mismatch on every dark load.
function getServerSnapshot(): Theme {
  return "light";
}

export function setTheme(theme: Theme): void {
  current = theme;
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Private window: the choice just doesn't persist. Not worth surfacing.
  }
  listeners.forEach((fn) => fn());
}

export function toggleTheme(): void {
  setTheme(current === "dark" ? "light" : "dark");
}

/** The current theme, and a toggle. Safe to call from any client component. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return { theme, toggle: toggleTheme };
}

/** Called once on mount by the palette. Reconciles the module store with
 *  what the inline script put on <html> before React ever ran. */
export function initTheme(): void {
  const fromDom = syncFromDocument();
  const stored = readStored();
  const resolved = stored ?? fromDom;
  if (resolved !== current || fromDom !== resolved) {
    current = resolved;
    document.documentElement.setAttribute("data-theme", resolved);
    listeners.forEach((fn) => fn());
  }
}
