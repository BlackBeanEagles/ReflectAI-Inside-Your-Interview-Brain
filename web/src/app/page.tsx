"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { friendlyError, isAbortError, useAbortSignal, useHealth } from "@/lib/hooks";
import type { CleanedResume, EvaluateResponse, ReportResponse, VoiceAnalysis } from "@/lib/types";
import {
  Alert,
  Card,
  PrimaryButton,
  ProgressTrack,
  ROUND_ACCENT,
  RoundBadge,
  RoundProgress,
  ScorePanel,
  SecondaryButton,
  Spinner,
  TextArea,
} from "@/components/ui";
import ReportView from "@/components/ReportView";
import { ResumePicker } from "@/components/ResumePicker";

const MAX_QUESTIONS = 10;

const ROLE_PRESETS = [
  "None",
  "Backend Engineer",
  "Frontend Engineer",
  "Full-Stack Engineer",
  "Data Scientist",
  "Data Analyst",
  "DevOps / SRE",
  "Mobile Developer",
  "QA / Test Engineer",
  "Product Manager",
  "General Software Engineer",
];

const LANGUAGE_PRESETS = [
  "English",
  "Spanish",
  "French",
  "German",
  "Portuguese",
  "Hindi",
  "Mandarin Chinese",
  "Japanese",
  "Arabic",
];

type Phase = "setup" | "interview" | "report";

function speakText(text: string) {
  if (!("speechSynthesis" in window)) {
    alert("Speech synthesis isn't supported in this browser.");
    return;
  }
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

function InterviewSessionInner() {
  const { token } = useAuth();
  const { health } = useHealth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // A reset-password email currently links to /?reset_token=... (see
  // reset-password/page.tsx for why) -- catch that here and forward it to
  // the real page instead of showing the interview setup screen underneath.
  useEffect(() => {
    const resetToken = searchParams.get("reset_token");
    if (resetToken) router.replace(`/reset-password?token=${encodeURIComponent(resetToken)}`);
  }, [searchParams, router]);

  const storageEnabled = health?.storage === "postgres";

  // ── Setup phase state ──────────────────────────────────────────────────
  const [phase, setPhase] = useState<Phase>("setup");
  const [resumeMethod, setResumeMethod] = useState<"paste" | "upload">("paste");
  const [resumeText, setResumeText] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [role, setRole] = useState("None");
  const [language, setLanguage] = useState("English");
  const [storeConsent, setStoreConsent] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [setupLoading, setSetupLoading] = useState(false);

  // ── Interview phase state ──────────────────────────────────────────────
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [cleaned, setCleaned] = useState<CleanedResume | null>(null);
  const [count, setCount] = useState(0);
  const [round, setRound] = useState("hr");
  const [difficulty, setDifficulty] = useState("medium");
  const [scoreHistory, setScoreHistory] = useState<number[]>([]);
  const [stressCount, setStressCount] = useState(0);
  const [usedSkills, setUsedSkills] = useState<string[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState<string | null>(null);
  const [transitionMessage, setTransitionMessage] = useState<string | null>(null);
  const [interviewComplete, setInterviewComplete] = useState(false);
  const [completionNotice, setCompletionNotice] = useState("");
  const [storedCount, setStoredCount] = useState(0);
  const [nextLoading, setNextLoading] = useState(false);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [questionStartedAt, setQuestionStartedAt] = useState<number | null>(null);

  // ── Answer + evaluation state ──────────────────────────────────────────
  const [answer, setAnswer] = useState("");
  const [evaluated, setEvaluated] = useState(false);
  const [evalResult, setEvalResult] = useState<EvaluateResponse | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);

  // ── Voice recording state ──────────────────────────────────────────────
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceAnalysis, setVoiceAnalysis] = useState<VoiceAnalysis | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // ── Report phase state ─────────────────────────────────────────────────
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  const nextStartSignal = useAbortSignal();
  const nextQuestionSignal = useAbortSignal();
  const nextEvalSignal = useAbortSignal();
  const nextReportSignal = useAbortSignal();

  // ── Setup: start interview ─────────────────────────────────────────────
  async function handleStart() {
    setSetupError(null);
    const hasInput = (resumeMethod === "paste" && resumeText.trim()) || (resumeMethod === "upload" && resumeFile);
    if (!hasInput) {
      setSetupError("Please paste your resume or upload a PDF first.");
      return;
    }
    const signal = nextStartSignal();
    setSetupLoading(true);
    try {
      const langValue = language !== "English" ? language : null;
      const roleValue = role !== "None" ? role : null;

      const { session_id } = await api.startSession(
        { store_consent: storeConsent, language: langValue },
        token,
        signal,
      );
      const { cleaned: cleanedData } = await api.parseResume(
        {
          text: resumeMethod === "paste" ? resumeText.trim() : undefined,
          file: resumeMethod === "upload" ? resumeFile! : undefined,
          sessionId: session_id,
        },
        signal,
      );

      setSessionId(session_id);
      setCleaned(cleanedData);
      setPhase("interview");

      // Fetch the first question immediately, same as the setup->interview
      // transition in the Streamlit app.
      await fetchNextQuestion({
        count: 0,
        round: "hr",
        difficulty: "medium",
        scoreHist: [],
        stressC: 0,
        used: [],
        cleanedOverride: cleanedData,
        sessionOverride: session_id,
        roleOverride: roleValue,
        langOverride: langValue,
      });
    } catch (err) {
      if (isAbortError(err)) return;
      setSetupError(friendlyError(err));
    } finally {
      if (!signal.aborted) setSetupLoading(false);
    }
  }

  const roleValueRef = useRef<string | null>(null);
  const langValueRef = useRef<string | null>(null);

  async function fetchNextQuestion(opts: {
    count: number;
    round: string;
    difficulty: string;
    scoreHist: number[];
    stressC: number;
    used: string[];
    cleanedOverride?: CleanedResume;
    sessionOverride?: string;
    roleOverride?: string | null;
    langOverride?: string | null;
  }) {
    const activeCleaned = opts.cleanedOverride || cleaned;
    const activeSession = opts.sessionOverride || sessionId;
    if (opts.roleOverride !== undefined) roleValueRef.current = opts.roleOverride;
    if (opts.langOverride !== undefined) langValueRef.current = opts.langOverride;
    if (!activeCleaned) return;

    const signal = nextQuestionSignal();
    setNextLoading(true);
    setInterviewError(null);
    try {
      const result = await api.nextQuestion(
        {
          count: opts.count,
          skills: activeCleaned.skills,
          projects: activeCleaned.projects,
          experience: activeCleaned.experience,
          used_skills: opts.used,
          current_round: opts.round,
          score_history: opts.scoreHist,
          difficulty: opts.difficulty,
          stress_count: opts.stressC,
          max_questions: MAX_QUESTIONS,
          session_id: activeSession || undefined,
          role: roleValueRef.current,
          language: langValueRef.current,
        },
        signal,
      );

      if (result.should_end) {
        setInterviewComplete(true);
        setCurrentQuestion(null);
        setCompletionNotice(result.decision_reason || "");
        return;
      }
      if (result.is_error) {
        setInterviewError(result.question);
        return;
      }

      const wasHr = opts.round === "hr";
      let newUsed = opts.used;
      if (result.round === "technical") {
        newUsed = [...opts.used];
        for (const skill of activeCleaned.skills) {
          if (result.question.toLowerCase().includes(skill.toLowerCase()) && !newUsed.includes(skill)) {
            newUsed.push(skill);
          }
        }
        setUsedSkills(newUsed);
      }

      if (wasHr && result.round === "technical") {
        setTransitionMessage(
          "Let's move into the technical portion — the next questions will focus on your skills and projects in more depth.",
        );
      } else if (result.round === "stress" && opts.round !== "stress") {
        setTransitionMessage(
          "We'll switch to a short rapid-fire stretch to see how you reason under a little more time pressure.",
        );
      } else {
        setTransitionMessage(null);
      }

      setCurrentQuestion(result.question);
      setRound(result.round);
      setCount(result.count);
      setDifficulty(result.difficulty);
      setStressCount(result.stress_count);
      setQuestionStartedAt(Date.now());
      setAnswer("");
      setEvaluated(false);
      setEvalResult(null);
      setVoiceAnalysis(null);
      setAudioBlob(null);
    } catch (err) {
      if (isAbortError(err)) return;
      setInterviewError(friendlyError(err));
    } finally {
      if (!signal.aborted) setNextLoading(false);
    }
  }

  // ── Voice recording ─────────────────────────────────────────────────────
  async function startRecording() {
    setVoiceError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        setAudioBlob(blob);
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setVoiceError("Couldn't access your microphone. Check browser permissions.");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  async function transcribeRecording() {
    if (!audioBlob) return;
    setTranscribing(true);
    setVoiceError(null);
    try {
      const result = await api.transcribeAudio(audioBlob);
      if (result.is_error) {
        setVoiceError(result.text);
      } else {
        setAnswer(result.text);
        setVoiceAnalysis(result.voice_analysis);
      }
    } catch (err) {
      setVoiceError(friendlyError(err));
    } finally {
      setTranscribing(false);
    }
  }

  // ── Evaluate answer ──────────────────────────────────────────────────────
  async function handleEvaluate() {
    if (!answer.trim() || !currentQuestion || !sessionId) return;
    const signal = nextEvalSignal();
    setEvalLoading(true);
    setEvalError(null);
    try {
      const langValue = language !== "English" ? language : null;
      const result = await api.evaluateAnswer(
        {
          question: currentQuestion,
          answer: answer.trim(),
          answer_type: round,
          language: langValue,
        },
        signal,
      );
      setEvalResult(result);
      setEvaluated(true);

      const responseTime = questionStartedAt ? (Date.now() - questionStartedAt) / 1000 : undefined;
      if (!result.error) {
        try {
          await api.addInteraction({
            session_id: sessionId,
            question: currentQuestion,
            answer: answer.trim(),
            round_type: round,
            scores: result.scores,
            final_score: result.final_score,
            feedback: result.feedback,
            response_time_seconds: responseTime,
            voice_analysis: voiceAnalysis || undefined,
          });
          setStoredCount((c) => c + 1);
          setScoreHistory((h) => [...h, result.final_score]);
        } catch {
          // Best-effort, same as the Streamlit app -- don't block the user
          // if session storage fails.
        }
      }
    } catch (err) {
      if (isAbortError(err)) return;
      setEvalError(friendlyError(err));
    } finally {
      if (!signal.aborted) setEvalLoading(false);
    }
  }

  function handleSkip() {
    fetchNextQuestion({
      count,
      round,
      difficulty,
      scoreHist: scoreHistory,
      stressC: stressCount,
      used: usedSkills,
    });
  }

  function handleNext() {
    fetchNextQuestion({
      count,
      round,
      difficulty,
      scoreHist: scoreHistory,
      stressC: stressCount,
      used: usedSkills,
    });
  }

  async function handleGenerateReport() {
    if (!sessionId) return;
    const signal = nextReportSignal();
    setReportLoading(true);
    setReportError(null);
    try {
      const result = await api.generateReport(sessionId, token, signal);
      setReport(result);
      setPhase("report");
    } catch (err) {
      if (isAbortError(err)) return;
      setReportError(friendlyError(err));
    } finally {
      if (!signal.aborted) setReportLoading(false);
    }
  }

  async function handleDownloadPdf() {
    if (!sessionId) return;
    setPdfLoading(true);
    try {
      const blob = await api.downloadReportPdf(sessionId, token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `interview_report_${sessionId.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setReportError(friendlyError(err));
    } finally {
      setPdfLoading(false);
    }
  }

  function handleResetInterview() {
    setPhase("setup");
    setSessionId(null);
    setCleaned(null);
    setCount(0);
    setRound("hr");
    setDifficulty("medium");
    setScoreHistory([]);
    setStressCount(0);
    setUsedSkills([]);
    setCurrentQuestion(null);
    setTransitionMessage(null);
    setInterviewComplete(false);
    setCompletionNotice("");
    setStoredCount(0);
    setAnswer("");
    setEvaluated(false);
    setEvalResult(null);
    setVoiceAnalysis(null);
    setAudioBlob(null);
    setReport(null);
    setReportError(null);
  }

  // ── Render: report phase ────────────────────────────────────────────────
  if (phase === "report" && report) {
    return (
      <div className="space-y-6 ri-fade-in">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ri-text-mute">
              Session complete
            </p>
            <h1 className="ri-hero-title text-3xl font-extrabold">Final Report</h1>
          </div>
          <div className="flex gap-2">
            <SecondaryButton onClick={handleDownloadPdf} disabled={pdfLoading}>
              {pdfLoading ? "Preparing…" : "⬇️ Download PDF"}
            </SecondaryButton>
            <SecondaryButton onClick={handleResetInterview}>↩ New interview</SecondaryButton>
          </div>
        </div>
        {reportError && <Alert kind="error">{reportError}</Alert>}
        <Card glow>
          <ReportView report={report} />
        </Card>
      </div>
    );
  }

  // ── Render: interview phase ─────────────────────────────────────────────
  if (phase === "interview") {
    return (
      <div className="space-y-5 ri-fade-in">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-bold">
                Question <span className="ri-gradient-text">{count}</span>
                <span className="text-ri-text-mute font-medium"> / {MAX_QUESTIONS}</span>
              </h1>
              <p className="mt-0.5 text-xs text-ri-text-mute">
                {storedCount} answer{storedCount !== 1 ? "s" : ""} saved to this session
              </p>
            </div>
            <SecondaryButton onClick={handleResetInterview}>↩ Reset</SecondaryButton>
          </div>
          {/* Turns "how much longer is this?" from a guess into a glance --
              and the bar takes the round's colour, so the escalation into
              technical and stress is visible in the chrome, not just the badge. */}
          <RoundProgress current={count} total={MAX_QUESTIONS} round={round} />
        </div>

        {transitionMessage && (
          <Alert kind="info">
            <span>{transitionMessage}</span>
          </Alert>
        )}

        {interviewComplete ? (
          <Card>
            <Alert kind="success">
              Interview session complete. {completionNotice} Generate your final report below when
              you&apos;re ready.
            </Alert>
            <div className="mt-4">
              <PrimaryButton onClick={handleGenerateReport} disabled={reportLoading}>
                {reportLoading ? "Generating report…" : "📊 Generate Final Report"}
              </PrimaryButton>
            </div>
            {reportError && (
              <div className="mt-3">
                <Alert kind="error">{reportError}</Alert>
              </div>
            )}
          </Card>
        ) : interviewError ? (
          <Alert kind="error">{interviewError}</Alert>
        ) : nextLoading && !currentQuestion ? (
          <Card glow>
            <Spinner label="Generating question… (first one takes longest while the model warms up)" />
            <div className="mt-3">
              <ProgressTrack />
            </div>
          </Card>
        ) : currentQuestion ? (
          <Card key={count} glow className="ri-rise">
            <RoundBadge round={round} />
            {/* The question panel is tinted by the active round rather than
                picking from three hardcoded class strings, so adding a round
                later only means adding a hue to ROUND_ACCENT. */}
            <div
              className="mt-3 rounded-xl border-l-[3px] p-4 text-base leading-relaxed"
              style={{
                borderLeftColor: ROUND_ACCENT[round] || ROUND_ACCENT.hr,
                background: `linear-gradient(100deg, color-mix(in srgb, ${
                  ROUND_ACCENT[round] || ROUND_ACCENT.hr
                } 9%, transparent), transparent 70%), var(--ri-surface-alt)`,
              }}
            >
              {currentQuestion}
            </div>
            <button
              onClick={() => speakText(currentQuestion)}
              className="ri-focus mt-2.5 rounded-lg text-sm text-ri-accent transition-opacity hover:opacity-75"
            >
              🔊 Listen to the question
            </button>

            {/* Voice recording */}
            <div className="mt-4 rounded-xl border border-ri-border bg-ri-surface-alt/40 p-3">
              <p className="mb-2 text-sm font-semibold">🎙️ Record your answer instead of typing</p>
              <div className="flex flex-wrap items-center gap-2">
                {!recording ? (
                  <SecondaryButton onClick={startRecording}>● Start recording</SecondaryButton>
                ) : (
                  <button
                    type="button"
                    onClick={stopRecording}
                    className="ri-pulse-ring ri-focus flex items-center gap-2 rounded-xl border px-4 py-2.5 font-semibold transition-colors"
                    style={{
                      color: "var(--ri-stress)",
                      borderColor: "color-mix(in srgb, var(--ri-stress) 45%, transparent)",
                      background: "color-mix(in srgb, var(--ri-stress) 10%, transparent)",
                    }}
                  >
                    <span
                      aria-hidden
                      className="inline-block h-2.5 w-2.5 rounded-sm"
                      style={{ background: "var(--ri-stress)" }}
                    />
                    Stop recording
                  </button>
                )}
                {audioBlob && !recording && (
                  <SecondaryButton onClick={transcribeRecording} disabled={transcribing}>
                    {transcribing ? "Transcribing…" : "📝 Transcribe into answer box"}
                  </SecondaryButton>
                )}
              </div>
              {voiceError && <div className="mt-2"><Alert kind="error">{voiceError}</Alert></div>}
              {voiceAnalysis && (
                <div className="mt-2 text-xs text-ri-text-mute space-y-0.5">
                  <p>
                    🗯️ {voiceAnalysis.filler_words.filler_count} filler word(s) (
                    {(voiceAnalysis.filler_words.filler_ratio * 100).toFixed(0)}%)
                    {voiceAnalysis.pace && ` · ⏱️ ${voiceAnalysis.pace.words_per_minute.toFixed(0)} wpm (${voiceAnalysis.pace.pace_label})`}
                    {voiceAnalysis.pauses && ` · ⏸️ ${voiceAnalysis.pauses.pause_count} pause(s)`}
                    {` · 🎯 Confidence: ${voiceAnalysis.confidence.confidence_score.toFixed(1)}/10`}
                    {" — based on your recording, not later edits to the text."}
                  </p>
                </div>
              )}
            </div>

            <div className="mt-4">
              <TextArea
                label="Your Answer"
                value={answer}
                onChange={setAnswer}
                placeholder="Type your answer here, or record it above…"
                rows={5}
              />
            </div>

            <div className="mt-4 flex gap-3">
              <PrimaryButton onClick={handleEvaluate} disabled={evaluated || evalLoading || !answer.trim()}>
                {evalLoading ? "Evaluating…" : "🧠 Evaluate My Answer"}
              </PrimaryButton>
              <SecondaryButton onClick={handleSkip} disabled={nextLoading}>
                Skip →
              </SecondaryButton>
            </div>

            {evalError && <div className="mt-3"><Alert kind="error">{evalError}</Alert></div>}

            {evalResult && (
              <div className="ri-rise mt-5 space-y-4 border-t border-ri-border pt-4">
                <div className="ri-stagger flex flex-wrap gap-3">
                  <ScorePanel label="Score" score={evalResult.final_score} />
                  {Object.entries(evalResult.scores).map(([dim, val]) => (
                    <ScorePanel key={dim} label={dim} score={val} />
                  ))}
                </div>
                <div className="ri-stagger space-y-2">
                  <FeedbackLine icon="✅" label="Strength" tone="var(--ri-good-line)">
                    {evalResult.feedback.strength}
                  </FeedbackLine>
                  <FeedbackLine icon="⚠️" label="Weakness" tone="var(--ri-warn-line)">
                    {evalResult.feedback.weakness}
                  </FeedbackLine>
                  <FeedbackLine icon="💡" label="Improvement" tone="var(--ri-violet)">
                    {evalResult.feedback.improvement}
                  </FeedbackLine>
                </div>
                <PrimaryButton onClick={handleNext} disabled={nextLoading}>
                  {nextLoading ? "Loading next question…" : "Next Question →"}
                </PrimaryButton>
              </div>
            )}
          </Card>
        ) : null}
      </div>
    );
  }

  // ── Render: setup phase ─────────────────────────────────────────────────
  return (
    <div className="space-y-7 ri-fade-in">
      <div className="py-6 text-center sm:py-10">
        <span className="ri-rise mb-5 inline-flex items-center gap-2 rounded-full border border-ri-border bg-ri-surface/60 px-3.5 py-1.5 text-xs font-medium text-ri-text-mute backdrop-blur-sm">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: "var(--ri-cyan)", boxShadow: "0 0 8px var(--ri-cyan)" }}
          />
          Adaptive AI interviewer · voice or text
        </span>
        <h1 className="ri-hero-title mx-auto mb-4 max-w-3xl text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-6xl">
          Practice the interview before it counts
        </h1>
        <p className="mx-auto max-w-xl text-ri-text-mute sm:text-lg">
          Paste or upload your resume and get a full adaptive mock interview — HR warm-up,
          technical questions tailored to your skills, and a stress round if you need the
          pressure-testing. Every answer gets instant AI feedback.
        </p>
      </div>

      <div className="ri-stagger grid grid-cols-2 gap-3 sm:grid-cols-4">
        <FeatureCard icon="💬" title="HR round" desc="2 warm-up behavioural questions" tone="azure" />
        <FeatureCard icon="🛠️" title="Technical round" desc="Adaptive difficulty from your resume" tone="indigo" />
        <FeatureCard icon="🔥" title="Stress round" desc="Rapid-fire if scores dip" tone="orchid" />
        <FeatureCard icon="📊" title="Final report" desc="Scores, patterns, cognitive profile" tone="coral" />
      </div>

      <Card glow iridescent>
        {setupError && (
          <div className="mb-4">
            <Alert kind="error">{setupError}</Alert>
          </div>
        )}

        <ResumePicker
          method={resumeMethod}
          onMethodChange={setResumeMethod}
          text={resumeText}
          onTextChange={setResumeText}
          file={resumeFile}
          onFileChange={setResumeFile}
          label="Your resume"
        />

        <div className="grid sm:grid-cols-2 gap-4 mt-5">
          <label className="block">
            <span className="block text-sm font-medium mb-1.5">Target role / industry preset (optional)</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full cursor-pointer rounded-xl border border-ri-border bg-ri-surface-mute/70 px-3.5 py-2.5 text-sm
                transition-all duration-200 focus:border-ri-accent focus:bg-ri-surface focus:outline-none
                focus:shadow-[0_0_0_4px_color-mix(in_srgb,var(--ri-accent)_16%,transparent)]"
            >
              {ROLE_PRESETS.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="block text-sm font-medium mb-1.5">Interview language (optional)</span>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full cursor-pointer rounded-xl border border-ri-border bg-ri-surface-mute/70 px-3.5 py-2.5 text-sm
                transition-all duration-200 focus:border-ri-accent focus:bg-ri-surface focus:outline-none
                focus:shadow-[0_0_0_4px_color-mix(in_srgb,var(--ri-accent)_16%,transparent)]"
            >
              {LANGUAGE_PRESETS.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </label>
        </div>

        {storageEnabled && (
          <label className="flex items-start gap-2 mt-4 text-sm">
            <input
              type="checkbox"
              checked={storeConsent}
              onChange={(e) => setStoreConsent(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              Save my resume and interview answers so I can review them later (otherwise everything
              is discarded when this session ends)
            </span>
          </label>
        )}

        <div className="mt-5">
          <PrimaryButton onClick={handleStart} disabled={setupLoading} className="w-full">
            {setupLoading ? "Parsing resume…" : "🚀 Start Interview"}
          </PrimaryButton>
        </div>
      </Card>
    </div>
  );
}

// Each card pulls one pigment straight from the spectrum, so the four of
// them read as a single gradient sampled at four points rather than four
// unrelated status colours.
const FEATURE_TONES = {
  azure: "var(--ri-azure)",
  indigo: "var(--ri-indigo)",
  orchid: "var(--ri-orchid)",
  coral: "var(--ri-coral)",
} as const;

function FeatureCard({
  icon,
  title,
  desc,
  tone,
}: {
  icon: string;
  title: string;
  desc: string;
  tone: keyof typeof FEATURE_TONES;
}) {
  const hue = FEATURE_TONES[tone];
  return (
    <div
      className="ri-lift group rounded-2xl border p-4 backdrop-blur-sm"
      style={{
        borderColor: `color-mix(in srgb, ${hue} 26%, transparent)`,
        background: `linear-gradient(150deg, color-mix(in srgb, ${hue} 13%, transparent), transparent 62%), color-mix(in srgb, var(--ri-surface) 55%, transparent)`,
      }}
    >
      <div
        className="mb-2.5 flex h-10 w-10 items-center justify-center rounded-xl text-lg
          transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6"
        style={{
          background: `linear-gradient(135deg, color-mix(in srgb, ${hue} 26%, transparent), color-mix(in srgb, ${hue} 8%, transparent))`,
          boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${hue} 30%, transparent)`,
        }}
      >
        {icon}
      </div>
      <div className="text-sm font-bold">{title}</div>
      <div className="mt-0.5 text-xs text-ri-text-mute">{desc}</div>
    </div>
  );
}

/** One line of per-answer feedback, colour-keyed so strength / weakness /
 *  improvement are separable at a glance instead of three identical
 *  paragraphs of body text. */
function FeedbackLine({
  icon,
  label,
  tone,
  children,
}: {
  icon: string;
  label: string;
  tone: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="flex items-start gap-2.5 rounded-xl border-l-[3px] bg-ri-surface-alt/50 px-3.5 py-2.5 text-sm"
      style={{ borderLeftColor: tone }}
    >
      <span aria-hidden className="mt-px shrink-0">
        {icon}
      </span>
      <span className="min-w-0">
        <b style={{ color: tone }}>{label}:</b> {children}
      </span>
    </div>
  );
}

export default function InterviewSessionPage() {
  return (
    <Suspense fallback={null}>
      <InterviewSessionInner />
    </Suspense>
  );
}
