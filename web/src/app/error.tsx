"use client";

// Route-level error boundary.
//
// Without this file a render crash anywhere under the layout shows Next's
// stock error screen -- in production, an unstyled "Application error: a
// client-side exception has occurred". For an app that is meant to be
// wrapped as a Play Store install, that reads as "this is broken" rather
// than "one page failed", and it offers the user nothing to do next.
//
// The layout still renders around this, so the header and its navigation
// survive: the user is never stranded on a dead page.

import { useEffect, useState } from "react";
import Link from "next/link";
import { RotateCcw } from "lucide-react";
import { Card, PrimaryButton } from "@/components/ui";

// A chunk that will not load is almost never a bug in the page. It is what
// happens to a tab left open across a deploy: the page asks for a code file
// from the build it was loaded with, and that build is gone. "Try again"
// cannot fix it -- reset() re-renders with the same stale chunk map -- but
// a full reload fetches the new build and works. So it reloads once by
// itself, which is what anyone would do anyway.
const CHUNK_ERROR = /ChunkLoadError|Loading chunk|Failed to load chunk/i;

// Reloading on every chunk error would loop forever if the server is
// actually down. Allowing one automatic reload per window covers the
// deploy case and gives up on the outage case, where the message below is
// the honest outcome.
const RELOAD_KEY = "reflectinterview_chunk_reload_at";
const RELOAD_WINDOW_MS = 30_000;

function shouldAutoReload(): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY) || 0);
    return Date.now() - last > RELOAD_WINDOW_MS;
  } catch {
    // Storage blocked: no way to guard against a loop, so do not start one.
    return false;
  }
}

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const isChunkError = CHUNK_ERROR.test(`${error.name} ${error.message}`);
  // Decided once, at mount. Read during render rather than set from an
  // effect, so the first paint already says "updating" instead of flashing
  // the error card before the reload.
  const [reloading] = useState(() => isChunkError && shouldAutoReload());

  useEffect(() => {
    if (reloading) {
      try {
        sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
      } catch {
        /* checked in shouldAutoReload; unreachable in practice */
      }
      window.location.reload();
      return;
    }
    // Nothing collects these yet, so the console is genuinely where this
    // has to go -- swallowing it silently would make an in-the-wild report
    // unactionable. `digest` is the only handle on the server-side stack,
    // which Next strips from the client bundle in production.
    console.error("Route error:", error, error.digest);
  }, [error, reloading]);

  if (reloading) {
    return (
      <div className="mx-auto max-w-lg pt-6" role="status">
        <p className="text-sm text-ri-text-mute">Loading the latest version…</p>
      </div>
    );
  }

  return (
    <div className="ri-enter mx-auto max-w-lg pt-6">
      <Card>
        <h1 className="ri-title text-xl">
          {isChunkError ? "This page couldn't finish loading" : "That page hit an error"}
        </h1>
        <p className="ri-prose mt-2 text-sm text-ri-text-mute">
          {isChunkError
            ? "Part of the app didn't download — usually a dropped connection, or the app was updated while this tab was open. Reloading normally fixes it."
            : "Something failed while rendering. Your interview session is stored in this browser, so trying again usually picks up where you left off."}
        </p>
        {error.digest && (
          <p className="mt-3 font-mono text-xs text-ri-text-mute">
            Reference: {error.digest}
          </p>
        )}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <PrimaryButton onClick={isChunkError ? () => window.location.reload() : reset}>
            <RotateCcw size={15} strokeWidth={1.75} aria-hidden />
            {isChunkError ? "Reload" : "Try again"}
          </PrimaryButton>
          <Link href="/" className="ri-focus rounded-md text-sm text-ri-text-mute hover:text-ri-text">
            Back to the interview
          </Link>
        </div>
      </Card>
    </div>
  );
}
