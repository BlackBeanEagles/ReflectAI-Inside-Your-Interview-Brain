// Thin fetch wrapper around the existing FastAPI backend -- no backend
// changes were needed to build this frontend; every endpoint here already
// existed and is used exactly as-is by the Streamlit app this replaces.

import type {
  ApiErrorBody,
  ATSScoreResponse,
  EvaluateResponse,
  HealthResponse,
  NextQuestionResponse,
  PredictQuestionsResponse,
  ReportResponse,
  ResumeParseResponse,
  SessionStartResponse,
  TokenResponse,
  TranscribeResponse,
  UserHistoryResponse,
  User,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://reflectinterview-api.onrender.com";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body: ApiErrorBody = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((d) => d.msg).join("; ");
    }
  } catch {
    // Response wasn't JSON -- fall through to the generic message below.
  }
  return `Request failed (${res.status})`;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    throw new ApiError(await parseErrorDetail(res), res.status);
  }
  return res.json() as Promise<T>;
}

function jsonInit(body: unknown, signal?: AbortSignal): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  };
}

// ─── Health ──────────────────────────────────────────────────────────────

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

// ─── Auth ────────────────────────────────────────────────────────────────

export function signup(email: string, password: string, name?: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/signup", jsonInit({ email, password, name: name || null }));
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", jsonInit({ email, password }));
}

export function getMe(token: string): Promise<User> {
  return request<User>("/auth/me", {}, token);
}

export function getAuthHistory(token: string): Promise<UserHistoryResponse> {
  return request<UserHistoryResponse>("/auth/history", {}, token);
}

export function forgotPassword(email: string): Promise<{ message: string }> {
  return request<{ message: string }>("/auth/forgot-password", jsonInit({ email }));
}

export function resetPassword(token: string, new_password: string): Promise<{ message: string }> {
  return request<{ message: string }>("/auth/reset-password", jsonInit({ token, new_password }));
}

// ─── Session ─────────────────────────────────────────────────────────────

export function startSession(
  opts: { store_consent?: boolean; language?: string | null } = {},
  authToken?: string | null,
  signal?: AbortSignal,
): Promise<SessionStartResponse> {
  return request<SessionStartResponse>(
    "/session/start",
    jsonInit({ store_consent: !!opts.store_consent, language: opts.language || null }, signal),
    authToken,
  );
}

export interface AddInteractionPayload {
  session_id: string;
  question: string;
  answer: string;
  round_type: string;
  scores: Record<string, number>;
  final_score: number;
  feedback: { strength: string; weakness: string; improvement: string };
  response_time_seconds?: number;
  voice_analysis?: unknown;
}

export function addInteraction(payload: AddInteractionPayload): Promise<unknown> {
  return request("/session/add-interaction", jsonInit(payload));
}

export function generateReport(
  sessionId: string,
  token?: string | null,
  signal?: AbortSignal,
): Promise<ReportResponse> {
  return request<ReportResponse>(`/session/${sessionId}/report`, { method: "POST", signal }, token);
}

export async function downloadReportPdf(sessionId: string, token?: string | null): Promise<Blob> {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_BASE}/session/${sessionId}/report/pdf`, { headers });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.blob();
}

// ─── Resume / interview flow ─────────────────────────────────────────────

export function parseResume(
  opts: { text?: string; file?: File; sessionId?: string },
  signal?: AbortSignal,
): Promise<ResumeParseResponse> {
  const form = new FormData();
  if (opts.file) form.append("file", opts.file);
  else if (opts.text) form.append("text", opts.text);
  if (opts.sessionId) form.append("session_id", opts.sessionId);
  return request<ResumeParseResponse>("/parse-resume", { method: "POST", body: form, signal });
}

export interface NextQuestionPayload {
  count: number;
  skills: string[];
  projects: string[];
  experience: string[];
  used_skills: string[];
  current_round: string;
  score_history: number[];
  difficulty: string;
  stress_count: number;
  max_questions: number;
  session_id?: string;
  role?: string | null;
  language?: string | null;
}

export function nextQuestion(payload: NextQuestionPayload, signal?: AbortSignal): Promise<NextQuestionResponse> {
  return request<NextQuestionResponse>("/next-question", jsonInit(payload, signal));
}

export function evaluateAnswer(
  payload: {
    question: string;
    answer: string;
    answer_type: string;
    coaching_hint?: string;
    language?: string | null;
  },
  signal?: AbortSignal,
): Promise<EvaluateResponse> {
  return request<EvaluateResponse>("/evaluate-answer", jsonInit(payload, signal));
}

export function transcribeAudio(blob: Blob): Promise<TranscribeResponse> {
  const form = new FormData();
  form.append("file", blob, "answer.webm");
  return request<TranscribeResponse>("/transcribe-audio", { method: "POST", body: form });
}

// ─── ATS score ───────────────────────────────────────────────────────────

export function scoreAts(
  opts: {
    jobDescription: string;
    text?: string;
    file?: File;
    includeRecruiterTake?: boolean;
  },
  signal?: AbortSignal,
): Promise<ATSScoreResponse> {
  const form = new FormData();
  form.append("job_description", opts.jobDescription);
  form.append("include_recruiter_take", String(!!opts.includeRecruiterTake));
  if (opts.file) form.append("file", opts.file);
  else if (opts.text) form.append("text", opts.text);
  return request<ATSScoreResponse>("/ats-score", { method: "POST", body: form, signal });
}

// ─── Predicted questions ─────────────────────────────────────────────────

export function predictQuestions(
  opts: {
    text?: string;
    file?: File;
    role?: string;
    jobDescription?: string;
    count?: number;
  },
  signal?: AbortSignal,
): Promise<PredictQuestionsResponse> {
  const form = new FormData();
  if (opts.file) form.append("file", opts.file);
  else if (opts.text) form.append("text", opts.text);
  if (opts.role) form.append("role", opts.role);
  if (opts.jobDescription) form.append("job_description", opts.jobDescription);
  form.append("count", String(opts.count ?? 10));
  return request<PredictQuestionsResponse>("/predict-questions", { method: "POST", body: form, signal });
}
