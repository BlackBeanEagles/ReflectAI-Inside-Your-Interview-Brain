"use client";

import type { ReportResponse } from "@/lib/types";
import RoundPath from "./RoundPath";
import Transcript from "./Transcript";
import { ScorePanel } from "./ui";

const COMPARISON_LABELS: Record<string, string> = {
  overall_score: "Overall",
  hr_score: "HR",
  technical_score: "Technical",
  stress_score: "Stress",
};

/** The backend returns strengths and strength_patterns (and the weakness
 *  equivalents) as separate lists, and in practice they overlap heavily --
 *  from a single evaluated answer the report rendered the same observation
 *  in three different coloured boxes. Merging them, case- and
 *  punctuation-insensitively, means each observation is stated once. */
function mergeUnique(...lists: string[][]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of lists.flat()) {
    const key = item.trim().toLowerCase().replace(/[.,;:!?]+$/, "");
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item.trim());
  }
  return out;
}

export default function ReportView({ report }: { report: ReportResponse }) {
  const cog = report.cognitive;
  const comparison = report.comparison;
  const voice = report.voice_insights;

  const allStrengths = mergeUnique(report.strengths, report.strength_patterns);
  const allWeaknesses = mergeUnique(report.weaknesses, report.weakness_patterns);

  return (
    <div className="space-y-6">
      {/* ── How the interview went ──
          The overall score, then the route the session took. Four equal
          panels used to sit here, which presented a conditional round as
          if it were a parallel one -- and drew an unreached stress round
          as an empty ring, i.e. as a missing or failed result. */}
      <section>
        <p className="ri-eyebrow mb-3">How the interview went</p>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-8">
          <div className="sm:w-36 sm:shrink-0">
            <ScorePanel label="Overall" score={report.overall_score} />
          </div>
          <div className="min-w-0 flex-1">
            <RoundPath
              hr={report.hr_score}
              technical={report.technical_score}
              stress={report.stress_score}
            />
          </div>
        </div>
        <p className="mt-3 text-xs text-ri-text-mute">
          Based on {report.total_questions} evaluated answer{report.total_questions !== 1 ? "s" : ""}
        </p>
      </section>

      {/* ── Comparison to own past sessions ── */}
      {comparison && (
        <section>
          <h3 className="ri-eyebrow mb-3">Compared to your past sessions</h3>
          <div className="flex gap-3 flex-wrap">
            {Object.entries(comparison).map(([field, data]) => {
              const up = data.delta > 0;
              const flat = data.delta === 0;
              return (
                <div
                  key={field}
                  className="flex-1 min-w-[100px] bg-ri-surface-alt border border-ri-border rounded-xl p-3 text-center"
                >
                  <div
                    className="text-xl font-extrabold"
                    style={{ color: flat ? "var(--ri-text-mute)" : up ? "var(--ri-good-line)" : "var(--ri-stress)" }}
                  >
                    {/* This used to be preceded by {flat ? "" : up ? "" : ""} --
                        what was left of an up/down glyph after the emoji
                        were removed, still rendering a stray space before
                        every number. The sign already carries direction. */}
                    {data.delta > 0 ? "+" : ""}
                    {data.delta.toFixed(1)}
                  </div>
                  <div className="text-xs text-ri-text-mute uppercase tracking-wide font-semibold mt-1">
                    {COMPARISON_LABELS[field] || field}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-ri-text-mute mt-2">
            Based on your own prior saved sessions — not a comparison to other candidates.
          </p>
        </section>
      )}

      {/* ── Voice & delivery ── */}
      {voice && (
        <section>
          <h3 className="ri-eyebrow mb-3">Voice &amp; delivery</h3>
          <p className="text-xs text-ri-text-mute mb-3">
            Based on {voice.voiced_answer_count} voice-recorded answer{voice.voiced_answer_count !== 1 ? "s" : ""} in this session.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Filler words" value={String(voice.total_filler_words)}
              sub={`${(voice.avg_filler_ratio * 100).toFixed(0)}% of words avg.`} />
            <Stat label="Avg. pace" value={voice.avg_words_per_minute != null ? `${voice.avg_words_per_minute.toFixed(0)} wpm` : "N/A"} />
            <Stat label="Hesitation pauses" value={voice.total_hesitation_pauses != null ? String(voice.total_hesitation_pauses) : "N/A"} />
            <Stat label="Confidence" value={voice.avg_confidence_score != null ? `${voice.avg_confidence_score.toFixed(1)}/10` : "N/A"} />
          </div>
          {voice.recurring_signals.length > 0 && (
            <div className="mt-3">
              <p className="text-sm font-semibold mb-1">Recurring patterns</p>
              <ul className="space-y-1">
                {voice.recurring_signals.map((s, i) => (
                  <ListItem key={i} kind="pattern">{s}</ListItem>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-ri-text-mute mt-2 italic">
            Confidence is a heuristic from filler words, pace, and pauses in your recordings — not a
            validated psychological measurement.
          </p>
        </section>
      )}

      {/* ── The interviewer's note ──
          The same ruled paper the questions were asked on. During the
          interview the page showed you being written down; this is what
          got written. That continuity is the point -- a tinted info box
          said "system message", which is not what a debrief is. */}
      {report.summary && (
        <section>
          <p className="ri-eyebrow mb-2">Interviewer&apos;s note</p>
          <p className="ri-ruled ri-ruled-margin py-1 pr-2 text-[15px] text-ri-text">
            {report.summary}
          </p>
        </section>
      )}

      {/* ── The evidence, right under the verdict ──
          transcript is undefined only on a report saved before answers
          were kept with it; [] means a session with nothing answered. The
          note is worded to be true either way, including against an API
          that has not been redeployed yet. */}
      {report.transcript && report.transcript.length > 0 ? (
        <Transcript items={report.transcript} />
      ) : report.transcript === undefined && report.total_questions > 0 ? (
        <p className="text-xs text-ri-text-mute">
          Answer-by-answer detail isn&apos;t available for this report.
        </p>
      ) : null}

      {/* ── Behavioural analysis ── */}
      {(report.consistency || report.pressure_performance || report.behavior_summary || report.behavior_tags.length > 0) && (
        <section>
          <h3 className="ri-eyebrow mb-3">Behavioural analysis</h3>
          {report.behavior_tags.length > 0 && (
            <div className="flex gap-2 flex-wrap mb-3">
              {report.behavior_tags.map((t, i) => (
                <span key={i} className="px-2.5 py-1 rounded-full text-xs font-semibold bg-ri-chip-bg text-ri-chip-fg">
                  {t}
                </span>
              ))}
            </div>
          )}
          {report.consistency && <p className="text-sm mb-1"><b>Consistency:</b> {report.consistency}</p>}
          {report.pressure_performance && <p className="text-sm mb-3"><b>Under pressure:</b> {report.pressure_performance}</p>}
          {/* behavior_summary is cut, not restyled. Observed on a real report:
              it renders "Strong in Structure -- solid scores in 1/1 answers"
              and the Strengths list below it renders the same sentence
              verbatim. The report already carries two synthesised paragraphs
              that say something the lists do not -- report.summary at the top
              and the cognitive coach summary below -- so this third one was
              purely the bullets in prose form. */}
          {/* strength_patterns / weakness_patterns are merged into the
              Strengths and Weaknesses sections below rather than repeated
              here -- they overlap almost entirely in practice. */}
        </section>
      )}

      {/* ── Cognitive profile ── */}
      {cog && (
        <section>
          <h3 className="ri-eyebrow mb-3">Cognitive profile</h3>
          {cog.thinking_fingerprint && (
            <dl className="mb-4 grid gap-x-8 gap-y-3 sm:grid-cols-2">
              <TraitMeter label="Analytical depth" level={cog.thinking_fingerprint.analytical_depth} />
              <TraitMeter label="Clarity" level={cog.thinking_fingerprint.clarity} />
              <TraitMeter label="Consistency" level={cog.thinking_fingerprint.consistency} />
              <TraitMeter label="Confidence" level={cog.thinking_fingerprint.confidence} />
              <TraitMeter
                label="Impulsivity"
                level={cog.thinking_fingerprint.impulsivity}
                higherIsBetter={false}
              />
            </dl>
          )}
          {cog.thinking_style && (
            <p className="text-sm mb-2">
              <b>Thinking style:</b> <code className="bg-ri-surface-mute px-1.5 py-0.5 rounded">{cog.thinking_style}</code>{" "}
              (confidence {(cog.thinking_style_confidence * 100).toFixed(0)}%)
            </p>
          )}
          {cog.bias_summary && <p className="text-sm mb-2 italic text-ri-text-mute">{cog.bias_summary}</p>}
          {/* A second voice, so a second note: same paper as the
              interviewer's, with the margin rule in the accent colour so
              the two read as written by different people. It was the last
              tinted box left on this screen. */}
          {cog.cognitive_coach_summary && (
            <div className="mt-4">
              <p className="ri-eyebrow mb-2">Coach&apos;s note</p>
              <p
                className="ri-ruled ri-ruled-margin py-1 pr-2 text-sm text-ri-text"
                style={{ "--ri-margin-color": "var(--ri-accent)" } as React.CSSProperties}
              >
                {cog.cognitive_coach_summary}
              </p>
            </div>
          )}
        </section>
      )}

      {/* ── Debrief notes ──
          Strengths, weaknesses and recommendations were three stacks of
          coloured boxes -- green, amber, purple -- which is how a dashboard
          reports status, not how an interviewer reports on a person. They
          are one ruled sheet now, marked in the margin the way someone
          annotates notes: + for what landed, − for what did not, → for
          what to do next. The marks are symbols first and colour second,
          so the distinction survives greyscale and colour-blindness. */}
      {(allStrengths.length > 0 || allWeaknesses.length > 0 || report.recommendations.length > 0) && (
        <DebriefNotes
          strengths={allStrengths}
          weaknesses={allWeaknesses}
          recommendations={report.recommendations}
        />
      )}
      {/* "Patterns Detected" is cut rather than restyled: it repeated the
          Strengths and Weaknesses lists above it in different wording, and
          from a single evaluated answer the report was stating two facts in
          six boxes. Anything genuinely new in report.patterns still reaches
          the reader through the behavioural paragraph. */}
    </div>
  );
}

/**
 * One cognitive trait as a three-step meter.
 *
 * Stepped, NOT a percentage bar. The backend's build_thinking_fingerprint
 * returns Dict[str, str] -- literally the words "low", "medium" or "high"
 * from _score_to_tri_level. Rendering that as a smooth width:66% bar would
 * dress three buckets up as a continuous measurement and imply precision
 * that does not exist behind it. Three segments say exactly what is known.
 *
 * higherIsBetter is not decoration either: high impulsivity is a finding to
 * act on, while high clarity is a good result. Filling both in the same
 * colour would tell someone their impulsivity score is going well.
 */
function TraitMeter({
  label,
  level,
  higherIsBetter = true,
}: {
  label: string;
  level?: string | null;
  higherIsBetter?: boolean;
}) {
  const normalised = (level || "").trim().toLowerCase();
  const steps = normalised === "high" ? 3 : normalised === "medium" ? 2 : normalised === "low" ? 1 : 0;

  const favourable = higherIsBetter ? steps >= 3 : steps <= 1;
  const middling = steps === 2;
  const tone =
    steps === 0
      ? "var(--ri-border-strong)"
      : favourable
        ? "var(--ri-good-line)"
        : middling
          ? "var(--ri-warn-line)"
          : "var(--ri-stress)";

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <dt className="text-sm">{label}</dt>
        <dd className="text-xs font-medium capitalize" style={{ color: tone }}>
          {normalised || "not enough data"}
        </dd>
      </div>
      <div className="mt-1.5 flex gap-1" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className="h-1.5 flex-1 rounded-full transition-colors"
            style={{ background: i <= steps ? tone : "var(--ri-track)" }}
          />
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-ri-surface-alt border border-ri-border rounded-xl p-3 text-center">
      <div className="text-lg font-bold">{value}</div>
      <div className="text-xs text-ri-text-mute font-semibold uppercase tracking-wide mt-1">{label}</div>
      {sub && <div className="text-xs text-ri-text-mute mt-0.5">{sub}</div>}
    </div>
  );
}

type ItemKind = "strength" | "weakness" | "pattern" | "rec";

const ITEM_STYLES: Record<ItemKind, string> = {
  strength: "bg-ri-good-bg text-ri-good-fg border-ri-good-line",
  weakness: "bg-ri-warn-bg text-ri-warn-fg border-ri-warn-line",
  pattern: "bg-ri-info-bg text-ri-info-fg border-ri-info-line",
  rec: "bg-ri-purple-bg text-ri-purple-fg border-ri-purple-line",
};

function ListItem({ kind, children }: { kind: ItemKind; children: React.ReactNode }) {
  return (
    <li className={`text-sm px-3 py-2 rounded-lg border ${ITEM_STYLES[kind]}`}>{children}</li>
  );
}

const NOTE_MARKS = {
  strength: { mark: "+", color: "var(--ri-good-line)", heading: "What landed" },
  weakness: { mark: "−", color: "var(--ri-warn-line)", heading: "What didn't" },
  rec: { mark: "→", color: "var(--ri-accent)", heading: "Next time" },
} as const;

function DebriefNotes({
  strengths,
  weaknesses,
  recommendations,
}: {
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
}) {
  const groups = (
    [
      ["strength", strengths],
      ["weakness", weaknesses],
      ["rec", recommendations],
    ] as const
  ).filter(([, items]) => items.length > 0);

  return (
    <section>
      <p className="ri-eyebrow mb-2">Debrief notes</p>
      <div className="ri-ruled ri-ruled-margin pb-1 pr-2 text-sm text-ri-text">
        {groups.map(([kind, items]) => {
          const { mark, color, heading } = NOTE_MARKS[kind];
          return (
            // Headings and items are one rule-step tall each, so every line
            // of text -- including wrapped ones -- sits on a rule.
            <div key={kind}>
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ri-text-mute">
                {heading}
              </h3>
              <ul>
                {items.map((item, i) => (
                  <li key={i} className="flex gap-2">
                    <span
                      aria-hidden
                      className="w-3 shrink-0 text-center font-semibold"
                      style={{ color }}
                    >
                      {mark}
                    </span>
                    <span className="min-w-0">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}
