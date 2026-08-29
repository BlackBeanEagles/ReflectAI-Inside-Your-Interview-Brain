"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getHealth } from "./api";
import type { HealthResponse } from "./types";
import { ApiError } from "./api";

/** Every page here is a client component, so the App Router's usual
 * `export const metadata` (server-component-only) can't set a per-route
 * <title> -- this sets it directly instead, restoring the root layout's
 * title on unmount so navigating away doesn't leave a stale tab title.
 * Next's App Router re-asserts the layout's own title during/just after
 * hydration; retrying on a short interval for the first second beats that
 * race without needing a fragile fixed delay. */
export function usePageTitle(title: string) {
  useLayoutEffect(() => {
    const previous = document.title;
    document.title = title;

    let attempts = 0;
    const interval = setInterval(() => {
      attempts += 1;
      if (document.title !== title) document.title = title;
      if (attempts >= 10) clearInterval(interval);
    }, 100);

    return () => {
      clearInterval(interval);
      document.title = previous;
    };
  }, [title]);
}

/** Human-readable message from any thrown value -- fetch network errors,
 * ApiError (backend's {detail: "..."} body), or anything else. */
export function friendlyError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof TypeError) return "Cannot connect to the backend. Please try again.";
  if (err instanceof Error) return err.message;
  return "Something went wrong. Please try again.";
}

/** One logical async action (e.g. "submit this form") that can be
 * re-triggered before its previous call finished -- a slow network plus an
 * impatient re-click, a stale response resolving after the user has already
 * moved on. Call the returned function right before starting a new request:
 * it aborts whatever this same action still had in flight and returns a
 * fresh AbortSignal for the new one, so an old response can never overwrite
 * a newer one. Also aborts on unmount. Pass the signal to the api.* call,
 * and in the catch block bail out early via isAbortError(err) -- a request
 * that lost the race isn't a real error, so it shouldn't set error state or
 * (in a finally block) clear a loading flag that the newer request owns. */
export function useAbortSignal() {
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => controllerRef.current?.abort();
  }, []);

  return () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    return controller.signal;
  };
}

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/** Polls /health once on mount -- mirrors the status dot in the Streamlit
 * sidebar so the same "is the backend actually ready" signal exists here. */
export function useHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((h) => {
        if (!cancelled) setHealth(h);
      })
      .catch(() => {
        if (!cancelled) setHealth(null);
      })
      .finally(() => {
        if (!cancelled) setChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { health, checked };
}
