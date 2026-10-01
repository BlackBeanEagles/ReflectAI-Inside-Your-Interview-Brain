// The interview as the path it actually was.
//
// A session is not three parallel scores. It is a route: an HR warm-up,
// then a technical round that adapts to you, then -- only if your scores
// slip -- a stress round. The report and the history page both used to
// flatten that into equal columns, which lost the most informative fact
// about a session: how far it went.
//
// That matters most for the stress round. It is conditional, so a null
// stress score is not missing data. The old report drew it as an empty
// ring labelled "Stress", which reads as a failed or absent result, and
// the history table drew it as "—". This says what actually happened.
//
// It deliberately does NOT say "your scores held up". The stress round
// needs three post-HR answers averaging under five to trigger, so a
// session that ended after two questions never reaches it regardless of
// how it went. Stating the rule and letting the reader apply it is
// accurate in every case; claiming the good reading would be wrong in
// some of them.

import { ROUND_ACCENT, ROUND_LABEL, scoreColor } from "./ui";

type Stage = {
  key: "hr" | "technical" | "stress";
  short: string;
  score: number | null | undefined;
};

export default function RoundPath({
  hr,
  technical,
  stress,
  compact = false,
}: {
  hr: number | null | undefined;
  technical: number | null | undefined;
  stress: number | null | undefined;
  /** Single-line form for a list row: no captions, smaller type. */
  compact?: boolean;
}) {
  const stages: Stage[] = [
    { key: "hr", short: "HR", score: hr },
    { key: "technical", short: "Technical", score: technical },
    { key: "stress", short: "Stress", score: stress },
  ];

  // The furthest stage actually reached, so connectors after it render
  // as the road not taken rather than as a gap in the data.
  const lastReached = stages.reduce((acc, s, i) => (s.score != null ? i : acc), -1);

  // A readable sentence for screen readers. The visual is a diagram; the
  // diagram's meaning is a sequence, which is exactly what a sentence is.
  const spoken = stages
    .map((s) =>
      s.score != null
        ? `${ROUND_LABEL[s.key]} ${s.score.toFixed(1)}`
        : s.key === "stress"
          ? "stress round not triggered"
          : `${ROUND_LABEL[s.key]} not reached`,
    )
    .join(", ");

  return (
    <div role="img" aria-label={`Interview path: ${spoken}.`}>
      <ol className="flex items-start" aria-hidden>
        {stages.map((s, i) => {
          const reached = s.score != null;
          const accent = ROUND_ACCENT[s.key];
          const isLast = i === stages.length - 1;
          // The connector leading OUT of this stage is solid only if the
          // interview carried on to the next one.
          const continued = i < lastReached;

          return (
            <li key={s.key} className={`flex min-w-0 items-start ${isLast ? "" : "flex-1"}`}>
              <div className="flex min-w-0 flex-col items-center">
                <span
                  className={`flex items-center justify-center rounded-full border-2 transition-colors ${
                    compact ? "h-2.5 w-2.5" : "h-3.5 w-3.5"
                  }`}
                  style={{
                    borderColor: reached ? accent : "var(--ri-border-strong)",
                    background: reached ? accent : "transparent",
                  }}
                />
                {!compact && (
                  <span className="mt-1.5 whitespace-nowrap text-[11px] text-ri-text-mute">
                    {s.short}
                  </span>
                )}
                <span
                  className={`whitespace-nowrap font-semibold tabular-nums ${
                    compact ? "mt-1 text-[11px]" : "mt-0.5 text-sm"
                  }`}
                  style={{ color: reached ? scoreColor(s.score) : "var(--ri-text-mute)" }}
                >
                  {reached ? s.score!.toFixed(1) : s.key === "stress" ? "not triggered" : "—"}
                </span>
              </div>

              {!isLast && (
                <span
                  className={`mx-1.5 flex-1 ${compact ? "mt-[4px]" : "mt-[6px]"}`}
                  style={{
                    height: 2,
                    borderRadius: 999,
                    // Solid where the interview went; dashed where it
                    // stopped. The dash is the one thing here that is
                    // drawn rather than coloured, so it survives
                    // greyscale and colour-blindness alike.
                    background: continued
                      ? `linear-gradient(to right, ${accent}, ${ROUND_ACCENT[stages[i + 1].key]})`
                      : `repeating-linear-gradient(to right, var(--ri-border-strong) 0 4px, transparent 4px 8px)`,
                  }}
                />
              )}
            </li>
          );
        })}
      </ol>

      {!compact && stress == null && lastReached >= 0 && (
        <p className="mt-3 text-xs leading-relaxed text-ri-text-mute">
          The stress round only starts if your recent scores slip below 5, so it doesn&apos;t
          appear in every session.
        </p>
      )}
    </div>
  );
}
