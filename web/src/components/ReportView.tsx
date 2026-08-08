"use client";

import type { ReportResponse } from "@/lib/types";
import { ScorePanel } from "./ui";

const COMPARISON_LABELS: Record<string, string> = {
  overall_score: "Overall",
  hr_score: "HR",
  technical_score: "Technical",
  stress_score: "Stress",
};

export default function ReportView({ report }: { report: ReportResponse }) {
  const cog = report.cognitive;
  const comparison = report.comparison;
  const voice = report.voice_insights;

  return (
    <div className="space-y-6">
      {/* ── Overall performance ── */}
      <section>
        <h3 className="font-bold text-sm uppercase tracking-wide text-ri-text-mute mb-3">
          Overall Performance
        </h3>
        <div className="flex gap-3 flex-wrap">
          <ScorePanel label="Overall" score={report.overall_score} />
          <ScorePanel label="HR Round" score={report.hr_score} />
          <ScorePanel label="Technical" score={report.technical_score} />
          <ScorePanel label="Stress" score={report.stress_score} />
        </div>
        <p className="text-xs text-ri-text-mute mt-2">
          Based on {report.total_questions} evaluated answer{report.total_questions !== 1 ? "s" : ""}
        </p>
      </section>

      {/* ── Comparison to own past sessions ── */}
      {comparison && (
        <section>
          <h3 className="font-bold text-sm mb-3">📈 Compared to your past sessions</h3>
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
                    {flat ? "➡️" : up ? "🔼" : "🔽"} {data.delta > 0 ? "+" : ""}
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
          <h3 className="font-bold text-sm mb-3">🎙️ Voice & Delivery</h3>
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
          <h3 className="font-bold text-sm mb-3">🧠 Behavioural Analysis</h3>
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
          {report.behavior_summary && (
            <div className="bg-ri-surface-alt border border-ri-border rounded-xl p-4 text-sm">
              {report.behavior_summary}
            </div>
          )}
          {report.strength_patterns.length > 0 && (
            <div className="mt-3">
              <p className="text-sm font-semibold mb-1">Strength patterns</p>
              <ul className="space-y-1">
                {report.strength_patterns.map((s, i) => <ListItem key={i} kind="strength">{s}</ListItem>)}
              </ul>
            </div>
          )}
          {report.weakness_patterns.length > 0 && (
            <div className="mt-3">
              <p className="text-sm font-semibold mb-1">Weakness patterns</p>
              <ul className="space-y-1">
                {report.weakness_patterns.map((w, i) => <ListItem key={i} kind="weakness">{w}</ListItem>)}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* ── Cognitive profile ── */}
      {cog && (
        <section>
          <h3 className="font-bold text-sm mb-3">🧩 Cognitive Profile</h3>
          {cog.thinking_fingerprint && (
            <p className="text-sm mb-2">
              <b>Analytical depth:</b> {cog.thinking_fingerprint.analytical_depth || "—"} ·{" "}
              <b>Impulsivity:</b> {cog.thinking_fingerprint.impulsivity || "—"} ·{" "}
              <b>Clarity:</b> {cog.thinking_fingerprint.clarity || "—"} ·{" "}
              <b>Consistency:</b> {cog.thinking_fingerprint.consistency || "—"} ·{" "}
              <b>Confidence:</b> {cog.thinking_fingerprint.confidence || "—"}
            </p>
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
      {report.strengths.length > 0 && (
        <ListSection title="✅ Strengths" items={report.strengths} kind="strength" />
      )}
      {report.weaknesses.length > 0 && (
        <ListSection title="⚠️ Weaknesses" items={report.weaknesses} kind="weakness" />
      )}
      {report.patterns.length > 0 && (
        <ListSection title="🔍 Patterns Detected" items={report.patterns} kind="pattern" />
      )}
      {report.recommendations.length > 0 && (
        <ListSection title="💡 Recommendations" items={report.recommendations} kind="rec" />
      )}
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
