"use client";

import { useState } from "react";
import * as api from "@/lib/api";
import { friendlyError, isAbortError, useAbortSignal, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, TextArea } from "@/components/ui";
import { scoreColor } from "@/components/ui";
import { ResumePicker } from "@/components/ResumePicker";
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
  const nextCheckSignal = useAbortSignal();

  const hasJobDescription = jobDescription.trim().length > 0;

  async function handleCheck() {
    setError(null);
    // Job description is optional -- see services/ats_scorer.py. Only the
    // resume is actually required to check anything.
    if (!(method === "paste" ? text.trim() : file)) {
      setError("Please add your resume (paste or upload) before checking your score.");
      return;
    }
    const signal = nextCheckSignal();
    setLoading(true);
    setResult(null);
    try {
      const res = await api.scoreAts(
        {
          jobDescription: hasJobDescription ? jobDescription.trim() : undefined,
          text: method === "paste" ? text.trim() : undefined,
          file: method === "upload" ? file! : undefined,
          // Recruiter's take compares the resume against the job description --
          // nothing to compare without one, so it's ignored server-side either
          // way, but skip sending it too so the button label doesn't lie.
          includeRecruiterTake: wantRecruiterTake && hasJobDescription,
        },
        signal,
      );
      setResult(res);
    } catch (err) {
      // Superseded by a re-click while this was still in flight -- the
      // newer call already owns loading/result state, so this stale one
      // must not touch either.
      if (isAbortError(err)) return;
      setError(friendlyError(err));
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold mb-1">✅ ATS Score</h1>
        <p className="text-ri-text-mute text-sm">
          Check how a resume holds up against a specific job posting, the way a real ATS/resume
          screener actually evaluates candidates — weighted categories, each fully traceable.
          This is <b>not</b> an AI-guessed number: the same inputs always produce the same score.
          A job description is optional — add one to also get keyword-match scoring against that
          specific posting; without one you still get a full resume-readiness check.
        </p>
      </div>

      <Card>
        {error && (
          <div className="mb-4">
            <Alert kind="error">{error}</Alert>
          </div>
        )}
        <ResumePicker
          method={method}
          onMethodChange={setMethod}
          text={text}
          onTextChange={setText}
          file={file}
          onFileChange={setFile}
          label="Your resume"
        />
        <div className="mt-5">
          <TextArea
            label="Job description (optional)"
            value={jobDescription}
            onChange={setJobDescription}
            placeholder="Paste a job posting to also score keyword match against it — the more complete it is, the more accurate the match. Leave blank for a general resume-readiness check."
            rows={7}
          />
        </div>
        <label
          className={`flex items-start gap-2 mt-4 text-sm ${hasJobDescription ? "" : "opacity-50"}`}
        >
          <input
            type="checkbox"
            checked={wantRecruiterTake}
            disabled={!hasJobDescription}
            onChange={(e) => setWantRecruiterTake(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            Also get a recruiter&apos;s first impression (AI-generated, ~10-20s extra — subjective,
            not part of the score above){!hasJobDescription && " — needs a job description to compare against"}
          </span>
        </label>
        <div className="mt-5">
          <PrimaryButton onClick={handleCheck} disabled={loading} className="w-full">
            {loading
              ? wantRecruiterTake && hasJobDescription
                ? "Scoring resume + asking for a recruiter's first read…"
                : hasJobDescription
                  ? "Scoring resume against job description…"
                  : "Scoring resume…"
              : "✅ Check ATS Score"}
          </PrimaryButton>
        </div>
      </Card>

      {result && (
        <Card className="ri-fade-in">
          <div className="text-center mb-5">
            <div className="text-5xl font-extrabold" style={{ color: scoreColor(result.overall_score / 10) }}>
              {result.overall_score.toFixed(0)}
            </div>
            <div className="text-sm font-semibold text-ri-text-mute uppercase tracking-wide mt-1">
              Overall ATS Score — {result.rating}
            </div>
          </div>

          {!result.has_job_description && (
            <div className="mb-5">
              <Alert kind="info">
                This is a general resume-readiness check. Add a job description above and check
                again to also score keyword match against that specific posting (worth up to 40%
                of a full score) and get a recruiter&apos;s first read.
              </Alert>
            </div>
          )}

          <h3 className="font-bold text-sm mb-2">Category breakdown</h3>
          <div className="space-y-2 mb-5">
            {result.categories.map((cat) => (
              <div key={cat.key} className="flex items-center gap-3 text-sm">
                <span className="w-28 sm:w-48 shrink-0">{cat.label} ({cat.weight}%)</span>
                <div className="flex-1 h-2.5 rounded-full bg-ri-track overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${cat.score}%`, background: scoreColor(cat.score / 10) }}
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

          {result.has_job_description && result.keyword_importance.length > 0 && (
            <>
              <h3 className="font-bold text-sm mb-2">Keyword importance</h3>
              <div className="space-y-1.5 mb-5">
                {result.keyword_importance.slice(0, 12).map((kw, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm">
                    <span className={`w-24 sm:w-40 shrink-0 truncate ${kw.matched ? "" : "text-ri-text-mute"}`}>
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
            </>
          )}

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
