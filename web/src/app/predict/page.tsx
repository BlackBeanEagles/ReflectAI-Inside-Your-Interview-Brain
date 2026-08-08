"use client";

import { useState } from "react";
import * as api from "@/lib/api";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, TextArea, TextField } from "@/components/ui";
import type { PredictedQuestionItem } from "@/lib/types";

const CATEGORY_META: Record<string, { icon: string; label: string }> = {
  technical: { icon: "🛠️", label: "Technical" },
  hr: { icon: "💬", label: "HR" },
  behavioral: { icon: "🧭", label: "Behavioral" },
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePredict() {
    setError(null);
    const hasResume = method === "paste" ? text.trim() : file;
    if (!hasResume && !role.trim() && !jobDescription.trim()) {
      setError("Add at least a resume, a target role, or a job description.");
      return;
    }
    setLoading(true);
    setQuestions(null);
    try {
      const result = await api.predictQuestions({
        text: method === "paste" ? text.trim() || undefined : undefined,
        file: method === "upload" ? file || undefined : undefined,
        role: role.trim() || undefined,
        jobDescription: jobDescription.trim() || undefined,
        count,
      });
      if (result.error) {
        setError(result.message || "Could not generate questions right now.");
      } else {
        setQuestions(result.questions);
      }
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
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
        <h1 className="text-2xl font-extrabold mb-1">🔮 Predicted Interview Questions</h1>
        <p className="text-ri-text-mute text-sm">
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
          <div className="flex gap-2">
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
              label="Paste resume (optional)"
              value={text}
              onChange={setText}
              placeholder={"Skills:\nPython, Django\n\nProjects:\nChatbot using NLP"}
              rows={5}
            />
          ) : (
            <label className="block">
              <span className="block text-sm font-medium mb-1.5">Upload resume PDF (optional)</span>
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full text-sm"
              />
            </label>
          )}
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
            {loading ? "Generating likely interview questions…" : "🔮 Predict Questions"}
          </PrimaryButton>
        </div>
      </Card>

      {questions && (
        <Card>
          <p className="text-sm text-ri-text-mute mb-4">
            {questions.length} question(s) generated — grouped by category.
          </p>
          <div className="space-y-5">
            {grouped.map(({ cat, items }) => (
              <div key={cat}>
                <h3 className="font-bold text-sm mb-2">
                  {CATEGORY_META[cat].icon} {CATEGORY_META[cat].label}
                </h3>
                <ul className="space-y-2">
                  {items.map((q, i) => (
                    <li key={i} className="bg-ri-purple-bg border border-ri-purple-line rounded-lg px-3 py-2.5 text-sm">
                      <b>{q.question}</b>
                      <div className="text-xs opacity-80 mt-1">💡 {q.prep_tip}</div>
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
