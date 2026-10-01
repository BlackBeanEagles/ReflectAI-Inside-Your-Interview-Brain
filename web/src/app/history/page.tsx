"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, SecondaryButton, Spinner, scoreColor } from "@/components/ui";
import type { UserReportItem } from "@/lib/types";
import ReportView from "@/components/ReportView";
import RoundPath from "@/components/RoundPath";
import ScoreTrendChart from "@/components/ScoreTrendChart";

export default function HistoryPage() {
  usePageTitle("History — ReflectInterview");
  const { user, token } = useAuth();
  const [history, setHistory] = useState<UserReportItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function loadHistory() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.getAuthHistory(token);
      setHistory(result.reports);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // loadHistory's setState calls must not run synchronously in the effect
    // body itself (react-hooks/set-state-in-effect) -- deferring the call
    // into a microtask makes it a genuine "callback reacting to an external
    // system", same pattern as auth-context.tsx's restore().finally().
    if (token) Promise.resolve().then(() => loadHistory());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (!user) {
    // An empty state should say why it is empty and offer one action. This
    // was a single notice floating over several hundred pixels of nothing,
    // which tells a first-time visitor neither what History is for nor what
    // it will look like once it works.
    return (
      <div className="ri-enter mx-auto max-w-2xl space-y-6">
        <div>
          <h1 className="ri-display text-3xl">History</h1>
          <p className="ri-prose mt-2 text-ri-text-mute">
            Every saved session in one place: score trends across rounds, the questions you were
            asked, and how each answer was judged.
          </p>
        </div>

        <Card>
          <p className="ri-eyebrow">What appears here</p>
          <ul className="mt-3 space-y-2 text-sm text-ri-text-mute">
            <li>A trend line of overall, HR, technical and stress scores, session by session.</li>
            <li>Per-session reports you can reopen, with the full question-by-question breakdown.</li>
            <li>Each new report compared against your own earlier ones — never against other people.</li>
          </ul>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link
              href="/"
              className="ri-focus inline-flex min-h-10 items-center justify-center rounded-ri-control bg-ri-accent px-4 text-sm font-medium text-white transition-colors hover:bg-[var(--ri-accent-hover)]"
            >
              Start your first interview
            </Link>
            <Link
              href="/login"
              className="ri-focus inline-flex min-h-10 items-center justify-center rounded-ri-control border border-ri-border px-4 text-sm font-medium transition-colors hover:border-ri-border-strong hover:bg-ri-surface-alt"
            >
              Log in
            </Link>
          </div>
          <p className="mt-4 text-xs text-ri-text-mute">
            History needs an account, and a session only appears if you ticked the save option when
            starting it. Everything else in the app works without logging in.
          </p>
        </Card>
      </div>
    );
  }

  const chronological = history ? [...history].reverse() : [];
  const chartData = chronological.map((item, i) => ({
    index: i + 1,
    Overall: item.report.overall_score,
    HR: item.report.hr_score,
    Technical: item.report.technical_score,
    Stress: item.report.stress_score,
  }));

  const overallScores = chronological.map((h) => h.report.overall_score).filter((v) => v != null);
  const avg = overallScores.length ? overallScores.reduce((a, b) => a + b, 0) / overallScores.length : null;
  const best = overallScores.length ? Math.max(...overallScores) : null;
  const latest = overallScores.length ? overallScores[overallScores.length - 1] : null;
  const prev = overallScores.length >= 2 ? overallScores[overallScores.length - 2] : null;
  const delta = latest != null && prev != null ? latest - prev : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="ri-display text-3xl">Your interview history</h1>
        <p className="ri-prose mt-2 text-sm text-ri-text-mute">
          Showing saved sessions for <b>{user.name || user.email}</b> — only sessions you opted in
          to saving during setup appear here.
        </p>
      </div>

      <SecondaryButton onClick={loadHistory} disabled={loading}>
        {loading ? "Refreshing…" : "Refresh history"}
      </SecondaryButton>

      {error && <Alert kind="error">{error}</Alert>}

      {loading && !history && <Spinner label="Loading history…" />}

      {history && history.length === 0 && (
        <Alert kind="info">
          No saved interviews yet. Tick &quot;Save this session to my account&quot; when starting an
          interview to build history here.
        </Alert>
      )}

      {history && history.length > 0 && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Sessions saved" value={String(history.length)} />
            <Stat label="Average overall" value={avg != null ? avg.toFixed(1) : "N/A"} />
            <Stat label="Best overall" value={best != null ? best.toFixed(1) : "N/A"} />
            <Stat
              label="Latest overall"
              value={latest != null ? latest.toFixed(1) : "N/A"}
              delta={delta != null ? delta : undefined}
            />
          </div>

          <Card>
            <h3 className="font-bold text-sm mb-3">Score trend across your saved sessions</h3>
            {chartData.length >= 1 ? (
              <ScoreTrendChart data={chartData} />
            ) : (
              <p className="text-sm text-ri-text-mute">Not enough scored sessions yet to plot a trend.</p>
            )}
            <p className="text-xs text-ri-text-mute mt-2">
              X-axis is session order (oldest → newest), not calendar time — sessions can be days or
              minutes apart.
            </p>
          </Card>

          {/* One list, not two. Every session used to appear twice: once
              as a row in a table of scores, and again directly below as an
              expandable card with the same date and the same overall
              score. The table's per-round columns also printed "—" for any
              round a session never reached, which reads as missing data
              when for the stress round it is the normal outcome.

              Each row now carries the path its session took, so scanning
              the list answers the question the columns could not: which
              of these sessions went into a stress round, and did that
              stop happening as you practised. */}
          <section>
            <h3 className="mb-3 text-sm font-bold">Your sessions</h3>
            <ol className="space-y-2">
              {[...chronological].reverse().map((item, i) => {
                const n = chronological.length - i;
                const isOpen = expanded === item.session_id;
                const overall = item.report.overall_score;
                const panelId = `session-detail-${item.session_id}`;
                return (
                  <li key={item.session_id}>
                    <Card flush className="overflow-hidden">
                      <button
                        onClick={() => setExpanded(isOpen ? null : item.session_id)}
                        aria-expanded={isOpen}
                        aria-controls={panelId}
                        className="ri-focus grid w-full grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 px-4 py-3 text-left transition-colors hover:bg-ri-surface-alt sm:grid-cols-[2.5rem_9rem_4.5rem_1fr_auto]"
                      >
                        <span className="text-xs tabular-nums text-ri-text-mute">#{n}</span>
                        <span className="text-sm">
                          {item.created_at.slice(0, 16).replace("T", " ")}
                        </span>
                        <span
                          className="text-sm font-semibold tabular-nums"
                          style={{ color: scoreColor(overall) }}
                        >
                          {overall != null ? overall.toFixed(1) : "N/A"}
                        </span>
                        <span className="col-span-2 min-w-0 sm:col-span-1">
                          <RoundPath
                            compact
                            hr={item.report.hr_score}
                            technical={item.report.technical_score}
                            stress={item.report.stress_score}
                          />
                        </span>
                        <span className="hidden items-center gap-2 text-xs text-ri-text-mute sm:flex">
                          {item.report.total_questions} q
                          <ChevronDown
                            size={14}
                            strokeWidth={1.75}
                            aria-hidden
                            className={`transition-transform ${isOpen ? "rotate-180" : ""}`}
                          />
                        </span>
                      </button>
                      {isOpen && (
                        <div id={panelId} className="border-t border-ri-border px-4 pb-4 pt-4">
                          <ReportView report={item.report} />
                        </div>
                      )}
                    </Card>
                  </li>
                );
              })}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, delta }: { label: string; value: string; delta?: number }) {
  return (
    <div className="bg-ri-surface-alt border border-ri-border rounded-xl p-3 text-center">
      <div className="text-2xl font-extrabold">{value}</div>
      <div className="text-xs text-ri-text-mute font-semibold uppercase tracking-wide mt-1">{label}</div>
      {delta != null && (
        <div
          className="text-xs font-bold mt-1"
          style={{ color: delta >= 0 ? "var(--ri-good-line)" : "var(--ri-stress)" }}
        >
          {delta >= 0 ? "▲" : "▼"} {delta >= 0 ? "+" : ""}
          {delta.toFixed(1)}
        </div>
      )}
    </div>
  );
}
