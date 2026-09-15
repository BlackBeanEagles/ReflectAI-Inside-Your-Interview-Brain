"use client";

import { useState } from "react";
import * as api from "@/lib/api";
import { friendlyError, isAbortError, useAbortSignal, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, TextArea, TextField } from "@/components/ui";
import { ResumePicker } from "@/components/ResumePicker";
import type { PredictedQuestionItem } from "@/lib/types";

const CATEGORY_LABEL: Record<string, string> = {
  technical: "Technical",
  hr: "HR",
  behavioral: "Behavioral",
};

export default function PredictedQuestionsPage() {
  usePageTitle("Predicted Questions — ReflectInterview");
  const [role, setRole] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [method, setMethod] = useState<"paste" | "upload">("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [count, setCount] = useState(10);
  const [questions, setQuestions] = useState<PredictedQuestionItem[] | null>(null);
  const [requested, setRequested] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextPredictSignal = useAbortSignal();

  async function handlePredict() {
    setError(null);
    const hasResume = method === "paste" ? text.trim() : file;
    if (!hasResume && !role.trim() && !jobDescription.trim()) {
      setError("Add at least a resume, a target role, or a job description.");
      return;
    }
    const signal = nextPredictSignal();
    setLoading(true);
    setQuestions(null);
    try {
      const result = await api.predictQuestions(
        {
          text: method === "paste" ? text.trim() || undefined : undefined,
          file: method === "upload" ? file || undefined : undefined,
          role: role.trim() || undefined,
          jobDescription: jobDescription.trim() || undefined,
          count,
        },
        signal,
      );
      if (result.error) {
        setError(result.message || "Could not generate questions right now.");
      } else {
        setQuestions(result.questions);
        setRequested(result.requested || count);
      }
    } catch (err) {
      if (isAbortError(err)) return;
      setError(friendlyError(err));
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }

  const grouped = questions
    ? (["technical", "hr", "behavioral"] as const).map((cat) => ({
        cat,
        items: questions.filter((q) => q.category === cat),
      })).filter((g) => g.items.length > 0)
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="ri-display text-3xl">Predicted Interview Questions</h1>
        <p className="ri-prose mt-2 text-ri-text-mute text-sm">
          Get a list of interview questions you should prepare for, generated from your resume
          and/or a target role or job description. This is a <b>study tool</b> — a prep list to
          read through, separate from the live adaptive mock interview in the first tab.
        </p>
      </div>

      <Card>
        {error && (
          <div className="mb-4">
            <Alert kind="error">{error}</Alert>
          </div>
        )}
        <div className="space-y-4">
          <TextField
            label="Target role (optional)"
            value={role}
            onChange={setRole}
            placeholder="e.g. Backend Engineer, Data Analyst, DevOps Engineer"
          />
          <TextArea
            label="Job description (optional)"
            value={jobDescription}
            onChange={setJobDescription}
            placeholder="Paste a job posting to bias questions toward what this specific role needs."
            rows={4}
          />
          <ResumePicker
            method={method}
            onMethodChange={setMethod}
            text={text}
            onTextChange={setText}
            file={file}
            onFileChange={setFile}
            label="Resume"
            optional
          />
          <label className="block">
            <span className="block text-sm font-medium mb-1.5">How many questions? ({count})</span>
            <input
              type="range"
              min={5}
              max={20}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="w-full accent-[var(--ri-accent)]"
            />
          </label>
          <PrimaryButton onClick={handlePredict} disabled={loading} className="w-full">
            {loading ? "Generating likely interview questions…" : "Predict Questions"}
          </PrimaryButton>
        </div>
      </Card>

      {questions && (
        <Card className="ri-enter">
          <p className="text-sm text-ri-text-mute mb-4">
            {questions.length === 1 ? "1 question" : `${questions.length} questions`} generated,
            grouped by category.
            {questions.length < requested && (
              <>
                {" "}You asked for {requested}; near-duplicates were merged. Generating again
                usually produces a different set.
              </>
            )}
          </p>
          <div className="space-y-5">
            {grouped.map(({ cat, items }) => (
              <div key={cat}>
                <h3 className="font-bold text-sm mb-2">
                  {CATEGORY_LABEL[cat]}
                </h3>
                <ul className="space-y-2">
                  {items.map((q, i) => (
                    <li key={i} className="bg-ri-purple-bg border border-ri-purple-line rounded-lg px-3 py-2.5 text-sm">
                      <b>{q.question}</b>
                      <div className="text-xs opacity-80 mt-1">{q.prep_tip}</div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
