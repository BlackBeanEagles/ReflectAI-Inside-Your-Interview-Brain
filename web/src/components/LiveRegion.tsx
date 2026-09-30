"use client";

// The one live region, mounted once in the root layout.
//
// It has to be in the DOM from first render and stay there: a live region
// that is inserted at the same moment as its text is frequently missed,
// because assistive tech watches existing regions for changes rather than
// scanning for new ones.

import { useAnnouncement } from "@/lib/announce";

export default function LiveRegion() {
  const message = useAnnouncement();

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      // Visually hidden, not display:none -- a hidden region is ignored.
      // clip-path with a 1px box is the technique that survives both
      // screen readers and the "find in page" behaviour of mobile
      // browsers, where older negative-offset tricks can be announced at
      // the wrong time.
      style={{
        position: "absolute",
        width: "1px",
        height: "1px",
        margin: "-1px",
        padding: 0,
        overflow: "hidden",
        clipPath: "inset(50%)",
        whiteSpace: "nowrap",
        border: 0,
      }}
    >
      {message}
    </div>
  );
}
