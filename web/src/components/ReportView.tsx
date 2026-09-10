"use client";

import type { ReportResponse } from "@/lib/types";
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
      {/* ── Overall performance ── */}
      <section>
        <h3 className="font-bold text-sm uppercase tracking-wide text-ri-text-mute mb-3">
          Overall Performance
        </h3>
        <div className="flex gap-3 flex-wrap">
          <ScorePanel label="Overall" score={report.overall_score} />
          <ScorePanel label="HR Round" score={report.hr_score} round="hr" />
          <ScorePanel label="Technical" score={report.technical_score} round="technical" />
          <ScorePanel label="Stress" score={report.stress_score} round="stress" />
        </div>
        <p className="text-xs text-ri-text-mute mt-2">
          Based on {report.total_questions} evaluated answer{report.total_questions !== 1 ? "s" : ""}
        </p>
      </section>

      {/* ── Comparison to own past sessions ── */}
      {comparison && (
        <section>
          <h3 className="font-bold text-sm mb-3">Compared to your past sessions</h3>
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
                    {flat ? "" : up ? "" : ""} {data.delta > 0 ? "+" : ""}
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
          <h3 className="font-bold text-sm mb-3">Voice & Delivery</h3>
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

      {/* ── Summary ── */}
      {report.summary && (
        <section>
          <div className="bg-ri-info-bg border border-ri-info-line rounded-xl p-4 text-sm leading-relaxed">
            {report.summary}
          </div>
        </section>
      )}

      {/* ── Behavioural analysis ── */}
      {(report.consistency || report.pressure_performance || report.behavior_summary || report.behavior_tags.length > 0) && (
        <section>
          <h3 className="font-bold text-sm mb-3">Behavioural Analysis</h3>
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
          <h3 className="font-bold text-sm mb-3">Cognitive Profile</h3>
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
          {cog.cognitive_coach_summary && (
            <div className="bg-ri-purple-bg border border-ri-purple-line rounded-xl p-4 text-sm mt-2">
              {cog.cognitive_coach_summary}
            </div>
          )}
        </section>
      )}

      {/* ── Strengths / weaknesses / patterns / recommendations ── */}
      {allStrengths.length > 0 && (
        <ListSection title="Strengths" items={allStrengths} kind="strength" />
      )}
      {allWeaknesses.length > 0 && (
        <ListSection title="Weaknesses" items={allWeaknesses} kind="weakness" />
      )}
      {/* "Patterns Detected" is cut rather than restyled: it repeated the
          Strengths and Weaknesses lists above it in different wording, and
          from a single evaluated answer the report was stating two facts in
          six boxes. Anything genuinely new in report.patterns still reaches
          the reader through the behavioural paragraph. */}
      {report.recommendations.length > 0 && (
        <ListSection title="Recommendations" items={report.recommendations} kind="rec" />
      )}
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

function ListSection({ title, items, kind }: { title: string; items: string[]; kind: ItemKind }) {
  return (
    <section>
      <h3 className="font-bold text-sm mb-2">{title}</h3>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <ListItem key={i} kind={kind}>{item}</ListItem>
        ))}
      </ul>
    </section>
  );
}
