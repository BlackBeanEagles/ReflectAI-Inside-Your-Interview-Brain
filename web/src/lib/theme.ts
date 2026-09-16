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

import { writeString } from "./safe-storage";

export type Theme = "light" | "dark";

const THEME_KEY = "reflectinterview_theme";

// Seeded from the DOM at module load rather than defaulting to "light".
// The inline <head> script has already applied the stored choice by the
// time this module evaluates on the client, so reading the attribute is
// both correct and cheaper than a second localStorage round-trip -- and
// it means the very first client render of the header shows the right
// icon. Starting at "light" and correcting in an effect made a dark-theme
// user briefly see a moon labelled "Switch to dark theme" while already
// in dark. On the server document is undefined and "light" is right,
// since that is also what getServerSnapshot reports for hydration.
let current: Theme =
  typeof document !== "undefined" &&
  document.documentElement.getAttribute("data-theme") === "dark"
    ? "dark"
    : "light";

const listeners = new Set<() => void>();

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
  // A private window can't persist the choice; the theme still applies for
  // this tab, which is the part the user actually asked for.
  writeString(THEME_KEY, theme);
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
