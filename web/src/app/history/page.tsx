"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, SecondaryButton, Spinner } from "@/components/ui";
import type { UserReportItem } from "@/lib/types";
import ReportView from "@/components/ReportView";

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
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-extrabold">📊 Interview History Dashboard</h1>
        <Alert kind="info">
          <Link href="/login" className="underline font-semibold">Log in</Link> to see score trends
          across your past sessions. Anonymous use still works everywhere else — an account just
          lets your history follow you across visits.
        </Alert>
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
        <h1 className="text-2xl font-extrabold mb-1">📊 Interview History Dashboard</h1>
        <p className="text-sm text-ri-text-mute">
          Showing saved sessions for <b>{user.name || user.email}</b> — only sessions you opted in
          to saving during setup appear here.
        </p>
      </div>

      <SecondaryButton onClick={loadHistory} disabled={loading}>
        {loading ? "Refreshing…" : "🔄 Refresh history"}
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
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--ri-border)" />
                    <XAxis dataKey="index" stroke="var(--ri-text-mute)" fontSize={12} />
                    <YAxis domain={[0, 10]} stroke="var(--ri-text-mute)" fontSize={12} />
                    <Tooltip contentStyle={{ background: "var(--ri-surface)", border: "1px solid var(--ri-border)" }} />
                    <Line type="monotone" dataKey="Overall" stroke="var(--ri-accent)" strokeWidth={2} dot />
                    <Line type="monotone" dataKey="HR" stroke="var(--ri-info-line)" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="Technical" stroke="var(--ri-tech)" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="Stress" stroke="var(--ri-stress)" strokeWidth={1.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-ri-text-mute">Not enough scored sessions yet to plot a trend.</p>
            )}
            <p className="text-xs text-ri-text-mute mt-2">
              X-axis is session order (oldest → newest), not calendar time — sessions can be days or
              minutes apart.
            </p>
          </Card>

          <Card>
            <h3 className="font-bold text-sm mb-3">All saved sessions</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-ri-text-mute border-b border-ri-border">
                    <th className="py-2 pr-3">#</th>
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">Overall</th>
                    <th className="py-2 pr-3">HR</th>
                    <th className="py-2 pr-3">Technical</th>
                    <th className="py-2 pr-3">Stress</th>
                    <th className="py-2 pr-3">Questions</th>
                  </tr>
                </thead>
                <tbody>
                  {[...chronological].reverse().map((item, i) => (
                    <tr key={item.session_id} className="border-b border-ri-border last:border-0">
                      <td className="py-2 pr-3">{chronological.length - i}</td>
                      <td className="py-2 pr-3">{item.created_at.slice(0, 16).replace("T", " ")}</td>
                      <td className="py-2 pr-3">{item.report.overall_score?.toFixed(1) ?? "—"}</td>
                      <td className="py-2 pr-3">{item.report.hr_score?.toFixed(1) ?? "—"}</td>
                      <td className="py-2 pr-3">{item.report.technical_score?.toFixed(1) ?? "—"}</td>
                      <td className="py-2 pr-3">{item.report.stress_score?.toFixed(1) ?? "—"}</td>
                      <td className="py-2 pr-3">{item.report.total_questions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div>
            <h3 className="font-bold text-sm mb-3">Session details</h3>
            <div className="space-y-2">
              {history.map((item) => {
                const isOpen = expanded === item.session_id;
                const overall = item.report.overall_score;
                return (
                  <Card key={item.session_id} className="!p-0 overflow-hidden">
                    <button
                      onClick={() => setExpanded(isOpen ? null : item.session_id)}
                      className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-ri-surface-alt"
                    >
                      <span className="text-sm font-medium">
                        {item.created_at.slice(0, 16).replace("T", " ")} — Overall{" "}
                        {overall != null ? `${overall.toFixed(1)}/10` : "N/A"} ·{" "}
                        {item.report.total_questions} questions
                      </span>
                      <span className="text-ri-text-mute">{isOpen ? "▲" : "▼"}</span>
                    </button>
                    {isOpen && (
                      <div className="px-4 pb-4 pt-1 border-t border-ri-border">
                        <ReportView report={item.report} />
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          </div>
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
