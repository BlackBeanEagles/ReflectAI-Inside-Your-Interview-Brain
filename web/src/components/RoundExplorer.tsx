"use client";

// The landing page used to *describe* the four stages in four lines of prose.
// This shows one instead: pick a round, see a real question from it and what
// comes back. It replaces copy the visitor has to take on trust with the
// actual artefact, and it gives the page something to do before the visitor
// has committed anything.
//
// The exchanges below are illustrative samples, not live model output -- the
// real thing is generated from the visitor's own resume. They're labelled as
// examples in the UI so nobody reads them as a promise of exact wording.

import { useState } from "react";
import { ROUND_ACCENT } from "./ui";

type RoundKey = "hr" | "technical" | "stress" | "report";

const ROUNDS: {
  key: RoundKey;
  n: string;
  title: string;
  desc: string;
  question: string;
  detail: string;
  scores?: { label: string; value: number }[];
}[] = [
  {
    key: "hr",
    n: "01",
    title: "HR round",
    desc: "Two behavioural questions to open.",
    question:
      "Tell me about a time a project's requirements changed late, and how you handled the timeline.",
    detail:
      "Opens every session. Scored on structure, relevance, communication and confidence — the same four dimensions used throughout.",
    scores: [
      { label: "Structure", value: 8 },
      { label: "Relevance", value: 9 },
      { label: "Communication", value: 8 },
    ],
  },
  {
    key: "technical",
    n: "02",
    title: "Technical round",
    desc: "Difficulty adapts to how you answer.",
    question:
      "Your inventory service broadcasts over websockets. Walk me through what you'd check first when p99 latency triples during peak load.",
    detail:
      "Drawn from the skills and projects in your own resume, so the questions reference your actual work. Score well and it gets harder; struggle and it eases off.",
    scores: [
      { label: "Structure", value: 7 },
      { label: "Relevance", value: 8 },
      { label: "Communication", value: 7 },
    ],
  },
  {
    key: "stress",
    n: "03",
    title: "Stress round",
    desc: "Rapid-fire, only if your scores dip.",
    question:
      "You have thirty seconds. Your deploy broke production and your lead is asking for an ETA you don't have yet. What do you say?",
    detail:
      "Only triggers when your running scores start slipping — it isn't part of every session. Tests how you reason with less time than you'd like.",
    scores: [
      { label: "Structure", value: 6 },
      { label: "Relevance", value: 7 },
      { label: "Communication", value: 6 },
    ],
  },
  {
    key: "report",
    n: "04",
    title: "Report",
    desc: "Scores, recurring patterns, next steps.",
    question: "Across 8 answers: strong on structure, thin on quantified impact.",
    detail:
      "Per-round averages, recurring strengths and weaknesses, a cognitive profile, and a PDF you can keep. If you have an account, it's compared against your own past sessions.",
  },
];

function MiniScore({ label, value }: { label: string; value: number }) {
  const tone =
    value >= 7.5 ? "var(--ri-good-line)" : value >= 5 ? "var(--ri-warn-line)" : "var(--ri-stress)";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 w-14 overflow-hidden rounded-full bg-ri-track">
        <div
          className="h-full rounded-full transition-[width] duration-500 ease-out"
          style={{ width: `${value * 10}%`, background: tone }}
        />
      </div>
      <span className="text-[11px] text-ri-text-mute">{label}</span>
    </div>
  );
}

export default function RoundExplorer() {
  const [active, setActive] = useState<RoundKey>("hr");
  const round = ROUNDS.find((r) => r.key === active)!;
  const accent = ROUND_ACCENT[active] || "var(--ri-accent)";

  return (
    <div className="rounded-xl border border-ri-border bg-ri-surface">
      {/* Tablist, not four buttons: these are four views of one thing. Arrow
          keys move between them, which is what a tablist buys you for free
          once the roles are right. */}
      <div
        role="tablist"
        aria-label="Interview stages"
        className="flex overflow-x-auto border-b border-ri-border"
      >
        {ROUNDS.map((r) => {
          const on = r.key === active;
          return (
            <button
              key={r.key}
              role="tab"
              aria-selected={on}
              aria-controls={`round-panel-${r.key}`}
              id={`round-tab-${r.key}`}
              onClick={() => setActive(r.key)}
              className={`ri-focus group relative flex-1 shrink-0 px-4 py-3 text-left transition-colors ${
                on ? "bg-ri-surface" : "hover:bg-ri-surface-alt"
              }`}
            >
              <span className="flex items-baseline gap-2">
                <span
                  className="text-[11px] font-medium tabular-nums transition-colors"
                  style={{ color: on ? (ROUND_ACCENT[r.key] ?? accent) : "var(--ri-text-mute)" }}
                >
                  {r.n}
                </span>
                <span
                  className={`whitespace-nowrap text-[13px] transition-colors ${
                    on ? "font-semibold text-ri-text" : "text-ri-text-mute group-hover:text-ri-text"
                  }`}
                >
                  {r.title}
                </span>
              </span>
              {/* Underline sits on the tab it belongs to and takes that
                  round's colour, so the escalation is legible in the chrome. */}
              <span
                aria-hidden
                className="absolute inset-x-0 bottom-0 h-0.5 origin-left transition-transform duration-300"
                style={{
                  background: ROUND_ACCENT[r.key] ?? accent,
                  transform: on ? "scaleX(1)" : "scaleX(0)",
                }}
              />
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`round-panel-${active}`}
        aria-labelledby={`round-tab-${active}`}
        className="p-5"
      >
        {/* key={active} restarts the entrance animation on every switch, so
            the panel reads as replaced rather than silently rewritten. */}
        <div key={active} className="ri-enter">
          <p className="ri-eyebrow mb-2">
            {round.key === "report" ? "Example finding" : "Example question"}
          </p>
          <p
            className="border-l-2 pl-4 text-[15px] leading-relaxed"
            style={{ borderLeftColor: accent }}
          >
            {round.question}
          </p>

          {round.scores && (
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
              {round.scores.map((s) => (
                <MiniScore key={s.label} label={s.label} value={s.value} />
              ))}
            </div>
          )}

          <p className="mt-4 text-sm leading-relaxed text-ri-text-mute">{round.detail}</p>
        </div>
      </div>
    </div>
  );
}
