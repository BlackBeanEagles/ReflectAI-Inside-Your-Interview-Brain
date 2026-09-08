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
  CardBody,
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
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  Check,
  Download,
  Lightbulb,
  Mic,
  RotateCcw,
  Square,
  TriangleAlert,
  Volume2,
} from "lucide-react";

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
      <div className="ri-enter space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="ri-eyebrow">Session complete</p>
            <h1 className="ri-display mt-1 text-3xl">Final report</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <SecondaryButton onClick={handleDownloadPdf} disabled={pdfLoading}>
              <Download size={15} strokeWidth={1.75} aria-hidden />
              {pdfLoading ? "Preparing…" : "Download PDF"}
            </SecondaryButton>
            <SecondaryButton onClick={handleResetInterview}>
              <RotateCcw size={15} strokeWidth={1.75} aria-hidden />
              New interview
            </SecondaryButton>
          </div>
        </div>
        {reportError && <Alert kind="error">{reportError}</Alert>}
        <Card>
          <CardBody>
            <ReportView report={report} />
          </CardBody>
        </Card>
      </div>
    );
  }

  // ── Render: interview phase ─────────────────────────────────────────────
  if (phase === "interview") {
    return (
      <div className="ri-enter space-y-5">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="ri-title text-lg tabular-nums">
                Question {count}
                <span className="font-normal text-ri-text-mute"> of {MAX_QUESTIONS}</span>
              </h1>
              <p className="mt-0.5 text-xs text-ri-text-mute">
                {storedCount} answer{storedCount !== 1 ? "s" : ""} saved to this session
              </p>
            </div>
            <SecondaryButton onClick={handleResetInterview}>
              <RotateCcw size={15} strokeWidth={1.75} aria-hidden />
              Reset
            </SecondaryButton>
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
            <CardBody>
              <Alert kind="success">
                Interview session complete. {completionNotice} Generate your final report below when
                you&apos;re ready.
              </Alert>
              <div className="mt-4">
                <PrimaryButton onClick={handleGenerateReport} disabled={reportLoading}>
                  {reportLoading ? "Generating report…" : "Generate final report"}
                </PrimaryButton>
              </div>
              {reportError && (
                <div className="mt-3">
                  <Alert kind="error">{reportError}</Alert>
                </div>
              )}
            </CardBody>
          </Card>
        ) : interviewError ? (
          <Alert kind="error">{interviewError}</Alert>
        ) : nextLoading && !currentQuestion ? (
          <Card>
            <CardBody>
              <Spinner label="Generating question… the first one takes longest while the model warms up." />
              <div className="mt-4">
                <ProgressTrack />
              </div>
            </CardBody>
          </Card>
        ) : currentQuestion ? (
          <Card key={count} className="ri-enter">
            <CardBody>
              <RoundBadge round={round} />
              {/* The rule takes the active round's colour, so the escalation
                  shows in the question itself, not only in the label above it. */}
              <p
                className="mt-3 border-l-2 pl-4 text-[17px] leading-relaxed"
                style={{ borderLeftColor: ROUND_ACCENT[round] || ROUND_ACCENT.hr }}
              >
                {currentQuestion}
              </p>
              <button
                onClick={() => speakText(currentQuestion)}
                className="ri-focus mt-3 flex items-center gap-1.5 text-sm text-ri-text-mute transition-colors hover:text-ri-text"
              >
                <Volume2 size={15} strokeWidth={1.75} aria-hidden />
                Listen to the question
              </button>

              <div className="mt-5 space-y-3">
                <TextArea
                  label="Your answer"
                  value={answer}
                  onChange={setAnswer}
                  placeholder="Type your answer, or record it below…"
                  rows={5}
                />

                <div className="flex flex-wrap items-center gap-2">
                  {!recording ? (
                    <SecondaryButton onClick={startRecording}>
                      <Mic size={15} strokeWidth={1.75} aria-hidden />
                      Record instead
                    </SecondaryButton>
                  ) : (
                    <SecondaryButton onClick={stopRecording} className="!text-ri-stress">
                      {/* Recording is the one genuinely live state in the app,
                          so it is the one thing that pulses continuously. */}
                      <Square
                        size={13}
                        strokeWidth={1.75}
                        className="ri-rec"
                        fill="currentColor"
                        aria-hidden
                      />
                      Stop recording
                    </SecondaryButton>
                  )}
                  {audioBlob && !recording && (
                    <SecondaryButton onClick={transcribeRecording} disabled={transcribing}>
                      {transcribing ? "Transcribing…" : "Transcribe into answer"}
                    </SecondaryButton>
                  )}
                </div>

                {voiceError && <Alert kind="error">{voiceError}</Alert>}
                {voiceAnalysis && (
                  <p className="text-xs leading-relaxed text-ri-text-mute">
                    {voiceAnalysis.filler_words.filler_count} filler word
                    {voiceAnalysis.filler_words.filler_count !== 1 ? "s" : ""} (
                    {(voiceAnalysis.filler_words.filler_ratio * 100).toFixed(0)}% of words)
                    {voiceAnalysis.pace && ` · ${voiceAnalysis.pace.words_per_minute.toFixed(0)} wpm (${voiceAnalysis.pace.pace_label})`}
                    {voiceAnalysis.pauses && ` · ${voiceAnalysis.pauses.pause_count} pause${voiceAnalysis.pauses.pause_count !== 1 ? "s" : ""}`}
                    {` · confidence ${voiceAnalysis.confidence.confidence_score.toFixed(1)}/10`}
                    {" — measured from your recording, not from later edits to the text."}
                  </p>
                )}
              </div>

              {/* Stacked below sm: side by side the primary label wraps to two
                  lines on a 375px screen and stretches Skip to match. */}
              <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                <PrimaryButton
                  onClick={handleEvaluate}
                  disabled={evaluated || evalLoading || !answer.trim()}
                  className="w-full sm:w-auto"
                >
                  {evalLoading ? "Evaluating…" : "Evaluate answer"}
                </PrimaryButton>
                <SecondaryButton onClick={handleSkip} disabled={nextLoading} className="w-full sm:w-auto">
                  Skip
                </SecondaryButton>
              </div>

              {evalError && <div className="mt-3"><Alert kind="error">{evalError}</Alert></div>}

              {evalResult && (
                <div className="ri-enter mt-6 space-y-5 border-t border-ri-border pt-5">
                  {/* Grid, not flex-wrap: there are five panels, so wrapping
                      leaves the last alone on its row where flex-1 stretches it
                      to full width -- one giant ring beside two small ones. */}
                  <div className="ri-stagger grid grid-cols-2 gap-2.5 sm:flex sm:flex-wrap">
                    <ScorePanel label="Overall" score={evalResult.final_score} />
                    {Object.entries(evalResult.scores).map(([dim, val]) => (
                      <ScorePanel key={dim} label={dim} score={val} />
                    ))}
                  </div>
                  <dl className="ri-stagger space-y-3">
                    <FeedbackLine Icon={Check} label="Strength" tone="var(--ri-good-line)">
                      {evalResult.feedback.strength}
                    </FeedbackLine>
                    <FeedbackLine Icon={TriangleAlert} label="Weakness" tone="var(--ri-warn-line)">
                      {evalResult.feedback.weakness}
                    </FeedbackLine>
                    <FeedbackLine Icon={Lightbulb} label="Improvement" tone="var(--ri-accent)">
                      {evalResult.feedback.improvement}
                    </FeedbackLine>
                  </dl>
                  <PrimaryButton onClick={handleNext} disabled={nextLoading}>
                    {nextLoading ? "Loading next question…" : "Next question"}
                    <ArrowRight size={15} strokeWidth={1.75} aria-hidden />
                  </PrimaryButton>
                </div>
              )}
            </CardBody>
          </Card>
        ) : null}
      </div>
    );
  }

  // ── Render: setup phase ─────────────────────────────────────────────────
  return (
    <div className="ri-enter space-y-8">
      <div className="max-w-2xl pt-2 sm:pt-6">
        <p className="ri-eyebrow">Adaptive AI interviewer</p>
        <h1 className="ri-display mt-3 text-[2.25rem] sm:text-[3.25rem]">
          Practice the interview before it counts.
        </h1>
        <p className="ri-prose mt-4 text-[17px] leading-relaxed text-ri-text-mute">
          Paste your resume and get a full mock interview — an HR warm-up, technical questions
          drawn from your own projects, and a stress round if your scores start slipping. Every
          answer is scored and returned with specific feedback.
        </p>
      </div>

      <dl className="ri-stagger grid gap-x-8 gap-y-5 border-y border-ri-border py-6 sm:grid-cols-2 lg:grid-cols-4">
        <Stage n="01" title="HR round" desc="Two behavioural questions to open." />
        <Stage n="02" title="Technical round" desc="Difficulty adapts to how you answer." />
        <Stage n="03" title="Stress round" desc="Rapid-fire, only if your scores dip." />
        <Stage n="04" title="Report" desc="Scores, recurring patterns, next steps." />
      </dl>

      <Card>
        <CardBody>
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
              className="w-full cursor-pointer rounded-lg border border-ri-border bg-ri-surface px-3 py-2 text-sm
                transition-colors focus:border-ri-accent focus:outline-none focus:ring-2 focus:ring-ri-accent/25"
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
              className="w-full cursor-pointer rounded-lg border border-ri-border bg-ri-surface px-3 py-2 text-sm
                transition-colors focus:border-ri-accent focus:outline-none focus:ring-2 focus:ring-ri-accent/25"
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

        <div className="mt-6">
          <PrimaryButton onClick={handleStart} disabled={setupLoading} className="w-full">
            {setupLoading ? "Parsing resume…" : "Start interview"}
          </PrimaryButton>
        </div>
        </CardBody>
      </Card>
    </div>
  );
}

/** One stage of the interview, as a numbered definition-list entry rather
 *  than a card. Four boxed cards in a row is the default shape for this kind
 *  of content and reads as filler; a rule with numbered items reads as a
 *  sequence, which is what the four stages actually are. */
function Stage({ n, title, desc }: { n: string; title: string; desc: string }) {
  return (
    <div>
      <dt className="flex items-baseline gap-2">
        <span className="text-xs font-medium tabular-nums text-ri-text-mute">{n}</span>
        <span className="ri-title text-[15px]">{title}</span>
      </dt>
      <dd className="mt-1 text-sm leading-relaxed text-ri-text-mute">{desc}</dd>
    </div>
  );
}

/** One line of per-answer feedback. The icon and rule are tinted so
 *  strength / weakness / improvement are separable at a glance instead of
 *  three identical paragraphs of body text. */
function FeedbackLine({
  Icon,
  label,
  tone,
  children,
}: {
  Icon: LucideIcon;
  label: string;
  tone: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <Icon size={15} strokeWidth={2} className="mt-0.5 shrink-0" style={{ color: tone }} aria-hidden />
      <div className="min-w-0">
        <dt className="text-xs font-semibold" style={{ color: tone }}>
          {label}
        </dt>
        <dd className="mt-0.5 text-sm leading-relaxed text-ri-text-mute">{children}</dd>
      </div>
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
