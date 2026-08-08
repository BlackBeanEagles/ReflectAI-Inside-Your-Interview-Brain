"use client";

import { useState } from "react";
import * as api from "@/lib/api";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, ScorePanel, SecondaryButton, Spinner, TextArea } from "@/components/ui";
import type { CleanedResume, EvaluateResponse } from "@/lib/types";

export default function ResumeAnalysisPage() {
  usePageTitle("Resume Analysis — ReflectInterview");
  const [method, setMethod] = useState<"paste" | "upload">("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [cleaned, setCleaned] = useState<CleanedResume | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [question, setQuestion] = useState<string | null>(null);
  const [questionLoading, setQuestionLoading] = useState(false);
  const [answer, setAnswer] = useState("");
  const [evalResult, setEvalResult] = useState<EvaluateResponse | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);

  async function handleParse() {
    setError(null);
    if (!(method === "paste" ? text.trim() : file)) {
      setError("Please paste your resume or upload a PDF first.");
      return;
    }
    setLoading(true);
    setCleaned(null);
    setQuestion(null);
    try {
      const result = await api.parseResume({
        text: method === "paste" ? text.trim() : undefined,
        file: method === "upload" ? file! : undefined,
      });
      setCleaned(result.cleaned);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  function handleClear() {
    setText("");
    setFile(null);
    setCleaned(null);
    setQuestion(null);
    setError(null);
  }

  async function handleGenerateQuestion() {
    if (!cleaned) return;
    setQuestionLoading(true);
    setError(null);
    try {
      const result = await api.nextQuestion({
        count: 2,
        skills: cleaned.skills,
        projects: cleaned.projects,
        experience: cleaned.experience,
        used_skills: [],
        current_round: "technical",
        score_history: [],
        difficulty: "medium",
        stress_count: 0,
        max_questions: 10,
      });
      setQuestion(result.question);
      setAnswer("");
      setEvalResult(null);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setQuestionLoading(false);
    }
  }

  async function handleEvaluate() {
    if (!question || !answer.trim()) return;
    setEvalLoading(true);
    setError(null);
    try {
      const result = await api.evaluateAnswer({ question, answer: answer.trim(), answer_type: "technical" });
      setEvalResult(result);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setEvalLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold mb-1">📄 Resume Analysis</h1>
        <p className="text-ri-text-mute text-sm">
          Upload a PDF or paste text to inspect extracted data and get a technical question.
        </p>
      </div>

      <Card>
        {error && (
          <div className="mb-4">
            <Alert kind="error">{error}</Alert>
          </div>
        )}
        <div className="flex gap-2 mb-4">
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
            placeholder={"Skills:\nPython, Django\n\nProjects:\nChatbot\n\nExperience:\nInternship"}
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
        <div className="flex gap-3 mt-4">
          <PrimaryButton onClick={handleParse} disabled={loading}>
            {loading ? "Parsing…" : "🔍 Parse Resume"}
          </PrimaryButton>
          <SecondaryButton onClick={handleClear}>Clear</SecondaryButton>
        </div>
      </Card>

      {loading && <Spinner label="Parsing resume…" />}

      {cleaned && (
        <Card>
          <h2 className="font-bold mb-3">Extracted data</h2>
          <div className="grid sm:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="font-semibold text-ri-text-mute mb-1">Skills ({cleaned.skills.length})</p>
              <div className="flex flex-wrap gap-1.5">
                {cleaned.skills.map((s, i) => (
                  <span key={i} className="px-2 py-0.5 rounded-full bg-ri-chip-bg text-ri-chip-fg text-xs font-medium">{s}</span>
                ))}
              </div>
            </div>
            <div>
              <p className="font-semibold text-ri-text-mute mb-1">Projects ({cleaned.projects.length})</p>
              <ul className="space-y-1">{cleaned.projects.map((p, i) => <li key={i}>{p}</li>)}</ul>
            </div>
            <div>
              <p className="font-semibold text-ri-text-mute mb-1">Experience ({cleaned.experience.length})</p>
              <ul className="space-y-1">{cleaned.experience.map((e, i) => <li key={i}>{e}</li>)}</ul>
            </div>
          </div>

          <div className="mt-5 pt-4 border-t border-ri-border">
            <PrimaryButton onClick={handleGenerateQuestion} disabled={questionLoading}>
              {questionLoading ? "Generating…" : "⚡ Generate Question"}
            </PrimaryButton>
          </div>
        </Card>
      )}

      {question && (
        <Card>
          <div className="p-4 rounded-lg border-l-4 border-ri-tech bg-ri-surface-alt text-base">
            {question}
          </div>
          <div className="mt-4">
            <TextArea label="Your Answer" value={answer} onChange={setAnswer} rows={5} placeholder="Type your answer here…" />
          </div>
          <div className="mt-4">
            <PrimaryButton onClick={handleEvaluate} disabled={evalLoading || !answer.trim()}>
              {evalLoading ? "Evaluating…" : "🧠 Evaluate Answer"}
            </PrimaryButton>
          </div>
          {evalResult && (
            <div className="mt-5 border-t border-ri-border pt-4 space-y-3">
              <div className="flex gap-3 flex-wrap">
                <ScorePanel label="Score" score={evalResult.final_score} />
              </div>
              <p className="text-sm"><b>✅ Strength:</b> {evalResult.feedback.strength}</p>
              <p className="text-sm"><b>⚠️ Weakness:</b> {evalResult.feedback.weakness}</p>
              <p className="text-sm"><b>💡 Improvement:</b> {evalResult.feedback.improvement}</p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
