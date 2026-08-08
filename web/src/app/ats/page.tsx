"use client";

import { useState } from "react";
import * as api from "@/lib/api";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, TextArea } from "@/components/ui";
import { scoreColor } from "@/components/ui";
import type { ATSScoreResponse } from "@/lib/types";

export default function AtsScorePage() {
  usePageTitle("ATS Score — ReflectInterview");
  const [jobDescription, setJobDescription] = useState("");
  const [method, setMethod] = useState<"paste" | "upload">("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [wantRecruiterTake, setWantRecruiterTake] = useState(false);
  const [result, setResult] = useState<ATSScoreResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCheck() {
    setError(null);
    if (!jobDescription.trim()) {
      setError("Please paste a job description first.");
      return;
    }
    if (!(method === "paste" ? text.trim() : file)) {
      setError("Please paste your resume or upload a PDF first.");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await api.scoreAts({
        jobDescription: jobDescription.trim(),
        text: method === "paste" ? text.trim() : undefined,
        file: method === "upload" ? file! : undefined,
        includeRecruiterTake: wantRecruiterTake,
      });
      setResult(res);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold mb-1">✅ ATS Score</h1>
        <p className="text-ri-text-mute text-sm">
          Check how a resume scores against a specific job posting, the way a real ATS/resume
          screener actually evaluates candidates — 7 weighted categories, each fully traceable.
          This is <b>not</b> an AI-guessed number: the same resume + job description always
          produce the same score.
        </p>
      </div>

      <Card>
        {error && (
          <div className="mb-4">
            <Alert kind="error">{error}</Alert>
          </div>
        )}
        <TextArea
          label="Job description"
          value={jobDescription}
          onChange={setJobDescription}
          placeholder="Paste the full job posting here — the more complete it is, the more accurate the keyword match."
          rows={7}
        />
        <div className="flex gap-2 my-4">
          <button
            onClick={() => setMethod("paste")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium ${method === "paste" ? "bg-ri-accent text-white" : "border border-ri-border"}`}
          >
            Paste text
          </button>
          <button
            onClick={() => setMethod("upload")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium ${method === "upload" ? "bg-ri-accent text-white" : "border border-ri-border"}`}
          >
            Upload PDF
          </button>
        </div>
        {method === "paste" ? (
          <TextArea
            label="Paste resume"
            value={text}
            onChange={setText}
            placeholder={"Skills:\nPython, Django\n\nExperience:\nBackend developer…"}
            rows={7}
          />
        ) : (
          <label className="block">
            <span className="block text-sm font-medium mb-1.5">Upload resume PDF</span>
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm"
            />
          </label>
        )}
        <label className="flex items-start gap-2 mt-4 text-sm">
          <input
            type="checkbox"
            checked={wantRecruiterTake}
            onChange={(e) => setWantRecruiterTake(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            Also get a recruiter&apos;s first impression (AI-generated, ~10-20s extra — subjective,
            not part of the score above)
          </span>
        </label>
        <div className="mt-5">
          <PrimaryButton onClick={handleCheck} disabled={loading} className="w-full">
            {loading
              ? wantRecruiterTake
                ? "Scoring resume + asking for a recruiter's first read…"
                : "Scoring resume against job description…"
              : "✅ Check ATS Score"}
          </PrimaryButton>
        </div>
      </Card>

      {result && (
        <Card>
          <div className="text-center mb-5">
            <div className="text-5xl font-extrabold" style={{ color: scoreColor(result.overall_score / 10) }}>
              {result.overall_score.toFixed(0)}
            </div>
            <div className="text-sm font-semibold text-ri-text-mute uppercase tracking-wide mt-1">
              Overall ATS Score — {result.rating}
            </div>
          </div>

          <h3 className="font-bold text-sm mb-2">Category breakdown</h3>
          <div className="space-y-2 mb-5">
            {result.categories.map((cat) => (
              <div key={cat.key} className="flex items-center gap-3 text-sm">
                <span className="w-48 shrink-0">{cat.label} ({cat.weight}%)</span>
                <div className="flex-1 h-2.5 rounded-full bg-ri-track overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${cat.score * 10}%`, background: scoreColor(cat.score) }}
                  />
                </div>
                <span className="w-8 text-right font-semibold">{cat.score.toFixed(0)}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-ri-text-mute mb-4">ℹ️ {result.methodology}</p>

          {result.recruiter_take && (
            <div className="bg-ri-purple-bg border border-ri-purple-line rounded-xl p-4 text-sm mb-5">
              <b>🗣️ Recruiter&apos;s first read (AI-generated, subjective — not part of the score above)</b>
              <p className="mt-1">{result.recruiter_take}</p>
            </div>
          )}

          <h3 className="font-bold text-sm mb-2">Section ranking (0-10)</h3>
          <div className="flex gap-3 flex-wrap mb-5">
            {result.section_ranking.map((sec) => (
              <div key={sec.section} className="flex-1 min-w-[100px] bg-ri-surface-alt border border-ri-border rounded-xl p-3 text-center">
                <div className="text-xl font-bold" style={{ color: scoreColor(sec.score) }}>{sec.score.toFixed(1)}</div>
                <div className="text-xs text-ri-text-mute font-semibold uppercase tracking-wide mt-1">{sec.section}</div>
              </div>
            ))}
          </div>

          <h3 className="font-bold text-sm mb-2">Keyword importance</h3>
          <div className="space-y-1.5 mb-5">
            {result.keyword_importance.slice(0, 12).map((kw, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className={`w-40 shrink-0 truncate ${kw.matched ? "" : "text-ri-text-mute"}`}>
                  {kw.matched ? "✅" : "❌"} {kw.keyword}
                </span>
                <div className="flex-1 h-2 rounded-full bg-ri-track overflow-hidden">
                  <div
                    className="h-full rounded-full bg-ri-accent"
                    style={{ width: `${kw.importance_pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          {result.improvement_plan.length > 0 && (
            <div>
              <h3 className="font-bold text-sm mb-1">📈 Resume ROI — ranked by expected score gain</h3>
              <p className="text-xs text-ri-text-mute mb-3">
                Each estimated gain is computed exactly from that keyword&apos;s or check&apos;s share of its
                category&apos;s weight — not a separate guess. Fix the top of this list first.
              </p>
              <ul className="space-y-2">
                {result.improvement_plan.map((item, i) => {
                  const icon = item.priority === "high" ? "🔴" : item.priority === "medium" ? "🟡" : "🟢";
                  const style =
                    item.priority === "high"
                      ? "bg-ri-warn-bg border-ri-warn-line"
                      : item.priority === "medium"
                        ? "bg-ri-info-bg border-ri-info-line"
                        : "bg-ri-good-bg border-ri-good-line";
                  return (
                    <li key={i} className={`text-sm px-3 py-2 rounded-lg border ${style}`}>
                      <b>{icon} +{item.estimated_gain.toFixed(1)} pts [{item.category}]</b> — {item.action}
                      <div className="text-xs opacity-80 mt-0.5">{item.reason} · Effort: {item.effort}</div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
