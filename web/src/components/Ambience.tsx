"use client";

import type { CSSProperties } from "react";
import { ROUND_ACCENT } from "./ui";

/**
 * A soft wash behind the interview, tinted by the round in play.
 *
 * The round already shows on the badge, the question rule and the progress
 * bar. This puts it in the light of the room, so the escalation from HR
 * through technical to stress is something you feel before you read it --
 * which is the one thing colour can do that a label cannot.
 *
 * Fixed and non-interactive, at a negative z-index so it sits over the page
 * ground but under every piece of content. It is rendered from inside the
 * interview view, so it exists only while an interview does: the landing
 * page, the report and the other tools keep the plain warm ground.
 */
export function RoomAmbience({ round }: { round: string }) {
  const accent = ROUND_ACCENT[round] ?? ROUND_ACCENT.hr;
  return (
    <div
      className="ri-ambience"
      aria-hidden="true"
      style={
        {
          // Mixed down hard. At full strength a tint like this stops being
          // atmosphere and starts being a coloured page, which is the line
          // between "the room changed" and "something is wrong".
          "--ri-ambience-tint": `color-mix(in srgb, ${accent} 14%, transparent)`,
        } as CSSProperties
      }
    />
  );
}

/**
 * Paper grain, mounted once for the whole app.
 *
 * Does two jobs at once: it is what makes a flat colour read as a surface
 * rather than an absence of one, and it dithers away the banding that large
 * soft gradients produce on 8-bit displays. Static -- texture, not motion.
 */
export function Grain() {
  return <div className="ri-grain" aria-hidden="true" />;
}
