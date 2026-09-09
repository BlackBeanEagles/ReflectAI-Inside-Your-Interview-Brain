"use client";

// Served by the service worker when a navigation fails with no network. It
// must not depend on the API for anything, since by definition the API is
// unreachable when this renders.

import { WifiOff } from "lucide-react";
import { usePageTitle } from "@/lib/hooks";
import { Card, PrimaryButton } from "@/components/ui";

export default function OfflinePage() {
  usePageTitle("Offline — ReflectInterview");

  return (
    <div className="ri-enter mx-auto max-w-md pt-10">
      <Card>
        <WifiOff size={20} strokeWidth={1.75} className="text-ri-text-mute" aria-hidden />
        <h1 className="ri-title mt-3 text-lg">You&apos;re offline</h1>
        <p className="mt-2 text-sm leading-relaxed text-ri-text-mute">
          ReflectInterview needs a connection: every question, score and report is generated live,
          so there is nothing meaningful it can do without one.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-ri-text-mute">
          An interview you had in progress is saved on this device and will still be here when you
          reconnect.
        </p>
        <div className="mt-5">
          <PrimaryButton onClick={() => window.location.reload()}>Try again</PrimaryButton>
        </div>
      </Card>
    </div>
  );
}
