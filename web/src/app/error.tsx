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

import { useEffect } from "react";
import Link from "next/link";
import { RotateCcw } from "lucide-react";
import { Card, PrimaryButton } from "@/components/ui";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Nothing collects these yet, so the console is genuinely where this
    // has to go -- swallowing it silently would make an in-the-wild report
    // unactionable. `digest` is the only handle on the server-side stack,
    // which Next strips from the client bundle in production.
    console.error("Route error:", error, error.digest);
  }, [error]);

  return (
    <div className="ri-enter mx-auto max-w-lg pt-6">
      <Card>
        <h1 className="ri-title text-xl">That page hit an error</h1>
        <p className="ri-prose mt-2 text-sm text-ri-text-mute">
          Something failed while rendering. Your interview session is stored in this
          browser, so trying again usually picks up where you left off.
        </p>
        {error.digest && (
          <p className="mt-3 font-mono text-xs text-ri-text-mute">
            Reference: {error.digest}
          </p>
        )}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <PrimaryButton onClick={reset}>
            <RotateCcw size={15} strokeWidth={1.75} aria-hidden />
            Try again
          </PrimaryButton>
          <Link href="/" className="ri-focus rounded-md text-sm text-ri-text-mute hover:text-ri-text">
            Back to the interview
          </Link>
        </div>
      </Card>
    </div>
  );
}
