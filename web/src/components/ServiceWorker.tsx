"use client";

import { useEffect } from "react";

/**
 * Registers the offline-fallback service worker.
 *
 * Registration is deferred to the `load` event rather than firing during
 * hydration: fetching and installing a worker competes for bandwidth with the
 * page's own JS, and delaying it costs nothing because the worker only matters
 * on a LATER visit anyway -- it cannot help the navigation that installed it.
 *
 * Development is skipped entirely. A worker registered against a dev server
 * outlives it, and then keeps answering navigations on localhost long after
 * the server is gone, which produces a confusing "why is my app still up"
 * that has bitten enough people to be worth avoiding.
 */
export default function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;

    const register = () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // A failed registration costs the offline page and nothing else, so
        // there is no user-facing error worth raising here.
      });
    };

    if (document.readyState === "complete") {
      register();
      return;
    }
    window.addEventListener("load", register);
    return () => window.removeEventListener("load", register);
  }, []);

  return null;
}
