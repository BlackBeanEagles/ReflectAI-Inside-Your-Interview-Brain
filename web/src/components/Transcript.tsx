// The interview, answer by answer.
//
// Everything else in the report is a summary of this, and until now this
// was the one thing it never showed: the questions, what you actually
// said, and how each answer was judged, side by side. That is the part a
// practice tool is for -- "I said 'we just used Redis' three times" is only
// visible with the answers in front of you.
//
// Collapsed by default, one row per question with its score, so a ten-
// question session reads as a list you can scan for the weak one instead
// of a wall of text. Native <details>, so it opens with a keyboard, needs
// no script, and is announced as expandable without any ARIA of our own.

import { ROUND_ACCENT, ROUND_LABEL, scoreColor } from "./ui";
import type { TranscriptItem } from "@/lib/types";

const FEEDBACK = [
  ["strength", "+", "var(--ri-good-line)"],
  ["weakness", "−", "var(--ri-warn-line)"],
  ["improvement", "→", "var(--ri-accent)"],
] as const;

export default function Transcript({ items }: { items: TranscriptItem[] }) {
  // Only worth pointing at when there is something to compare it against.
  const lowest =
    items.length >= 2
      ? items.reduce((lo, it, i) => (it.final_score < items[lo].final_score ? i : lo), 0)
      : -1;

  return (
    <section>
      <p className="ri-eyebrow mb-1">Answer by answer</p>
      <p className="mb-3 text-xs text-ri-text-mute">
        Open a question to see what you said and how it was judged.
      </p>
      <ol className="space-y-2">
        {items.map((it, i) => {
          const accent = ROUND_ACCENT[it.round] || "var(--ri-accent)";
          return (
            <li key={i}>
              <details className="group rounded-[var(--ri-radius-control)] border border-ri-border bg-ri-surface">
                <summary className="ri-focus flex cursor-pointer list-none items-start gap-3 px-3 py-2.5 [&::-webkit-details-marker]:hidden">
                  <span className="mt-0.5 shrink-0 text-xs tabular-nums text-ri-text-mute">
                    Q{i + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-ri-text">{it.question}</span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-ri-text-mute">
                      <span style={{ color: accent }}>{ROUND_LABEL[it.round] || it.round}</span>
                      {i === lowest && (
                        // The one answer most worth rereading -- named, not
                        // only coloured, so it does not rely on colour.
                        <span className="rounded-full border border-ri-border px-1.5">lowest score</span>
                      )}
                    </span>
                  </span>
                  <span
                    className="shrink-0 text-sm font-semibold tabular-nums"
                    style={{ color: scoreColor(it.final_score) }}
                  >
                    {it.final_score.toFixed(1)}
                  </span>
                </summary>

                <div className="space-y-3 border-t border-ri-border px-3 pb-3 pt-3">
                  <div>
                    <p className="ri-eyebrow mb-1">Your answer</p>
                    {/* The same ruled paper the question was asked on: this
                        is what was written down while you talked. */}
                    <p
                      className="ri-ruled ri-ruled-margin whitespace-pre-wrap py-1 pr-2 text-sm text-ri-text"
                      style={{ "--ri-margin-color": accent } as React.CSSProperties}
                    >
                      {it.answer}
                    </p>
                  </div>
                  {FEEDBACK.some(([k]) => it.feedback[k]) && (
                    <ul className="space-y-1 text-sm">
                      {FEEDBACK.map(([k, mark, color]) =>
                        it.feedback[k] ? (
                          <li key={k} className="flex gap-2">
                            <span aria-hidden className="w-3 shrink-0 text-center font-semibold" style={{ color }}>
                              {mark}
                            </span>
                            {/* The mark is decorative, so the kind of note
                                is spelled out for screen readers. */}
                            <span className="min-w-0">
                              <span className="sr-only">{k}: </span>
                              {it.feedback[k]}
                            </span>
                          </li>
                        ) : null,
                      )}
                    </ul>
                  )}
                </div>
              </details>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
