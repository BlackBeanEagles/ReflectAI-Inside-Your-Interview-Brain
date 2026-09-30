"use client";

// A single polite live region for "your result is ready" announcements.
//
// Every async result in this app appeared silently: you press "Get ATS
// score", wait up to a minute, and a screen reader says nothing at all.
// The visible page changing is not an announcement -- the only things
// that were ever announced here were error alerts and the feedback
// acknowledgement.
//
// Two decisions worth stating:
//
// The live region holds a SHORT sentence, not the result panel itself.
// Wrapping a whole panel in aria-live means the entire thing is read out
// on every re-render, including the parts that did not change, which is
// worse than silence because it cannot be interrupted usefully. A summary
// sentence plus a focus move (see useResultFocus) lets the user hear that
// it arrived and then read it at their own pace.
//
// It is one module-level store rather than a region per page, because two
// live regions announcing at once interleave unpredictably. Same
// useSyncExternalStore shape as lib/theme.ts.

import { useSyncExternalStore } from "react";

let message = "";
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((fn) => fn());
}

/**
 * Announce a short sentence to screen readers.
 *
 * Re-announcing identical text is a no-op in most screen readers, since
 * the node's contents never changed. Clearing first forces the second
 * announcement -- relevant when someone re-runs a scorer and gets the
 * same number back, where silence would read as "nothing happened".
 */
export function announce(text: string): void {
  if (message === text) {
    message = "";
    emit();
  }
  // A frame's gap is enough for the clear to land as its own mutation.
  setTimeout(() => {
    message = text;
    emit();
  }, 50);
}

export function clearAnnouncement(): void {
  message = "";
  emit();
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function getSnapshot(): string {
  return message;
}

function getServerSnapshot(): string {
  return "";
}

export function useAnnouncement(): string {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
