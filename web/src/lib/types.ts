// TypeScript types mirroring the FastAPI backend's Pydantic schemas
// (models/schemas.py) one-to-one. Keeping field names identical to the
// backend means the API client below can pass responses straight through
// without a translation layer that could silently drift from reality.

export interface User {
  id: number;
  email: string;
  name: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface FeedbackDetail {
  strength: string;
  weakness: string;
  improvement: string;
}

export interface VoiceAnalysis {
  filler_words: {
    total_words: number;
    filler_count: number;
    filler_ratio: number;
    by_phrase: Record<string, number>;
  };
  pace: { words_per_minute: number; pace_label: string; duration_seconds: number } | null;
  pauses: { pause_count: number; longest_pause_seconds: number } | null;
  confidence: { confidence_score: number; signals: string[] };
}

export interface TranscribeResponse {
  text: string;
  is_error: boolean;
  voice_analysis: VoiceAnalysis | null;
}

export interface EvaluateResponse {
  scores: Record<string, number>;
  final_score: number;
  score_label: string;
  feedback: FeedbackDetail;
  error?: boolean;
}

export interface SessionStartResponse {
  session_id: string;
}

export interface NextQuestionResponse {
  question: string;
  round: string;
  count: number;
  is_error: boolean;
  difficulty: string;
  question_type: string;
  agent: string;
  average_score: number | null;
  last_score: number | null;
  stress_count: number;
  should_end: boolean;
  decision_reason: string;
  cognitive_thinking_style: string | null;
  cognitive_suggested_tone: string | null;
  cognitive_stress_hint: string | null;
}

export interface CleanedResume {
  skills: string[];
  projects: string[];
  experience: string[];
}

export interface ResumeParseResponse {
  raw: Record<string, unknown>;
  cleaned: CleanedResume;
}

export interface ComparisonField {
  current: number;
  past_average: number;
  delta: number;
  session_count: number;
}

export interface VoiceInsights {
  voiced_answer_count: number;
  avg_filler_ratio: number;
  total_filler_words: number;
  avg_words_per_minute: number | null;
  avg_confidence_score: number | null;
  total_hesitation_pauses: number | null;
  recurring_signals: string[];
}

export interface CognitiveBlock {
  thinking_fingerprint: Record<string, string>;
  thinking_style: string;
  thinking_style_confidence: number;
  bias_summary: string;
  cognitive_coach_summary: string;
  session_impulsivity_score: number;
  impulsivity_category: string;
}

export interface ReportResponse {
  overall_score: number;
  hr_score: number | null;
  technical_score: number | null;
  stress_score: number | null;
  total_questions: number;
  strengths: string[];
  weaknesses: string[];
  patterns: string[];
  recommendations: string[];
  summary: string;
  consistency: string;
  pressure_performance: string;
  strength_patterns: string[];
  weakness_patterns: string[];
  behavior_tags: string[];
  behavior_summary: string;
  cognitive: CognitiveBlock | null;
  comparison: Record<string, ComparisonField> | null;
  voice_insights: VoiceInsights | null;
}

export interface UserReportItem {
  session_id: string;
  report: ReportResponse;
  created_at: string;
}

export interface UserHistoryResponse {
  reports: UserReportItem[];
}

export interface ATSFormatCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface ATSCategory {
  key: string;
  label: string;
  weight: number;
  score: number;
  checks: ATSFormatCheck[];
}

export interface ATSKeywordItem {
  keyword: string;
  weight: number;
}

export interface ATSImprovementItem {
  priority: string;
  category: string;
  action: string;
  reason: string;
  estimated_gain: number;
  effort: string;
}

export interface ATSKeywordImportance {
  keyword: string;
  weight: number;
  importance_pct: number;
  matched: boolean;
}

export interface ATSSectionScore {
  section: string;
  score: number;
}

export interface ATSScoreResponse {
  overall_score: number;
  rating: string;
  has_job_description: boolean;
  categories: ATSCategory[];
  matched_keywords: ATSKeywordItem[];
  missing_keywords: ATSKeywordItem[];
  keyword_importance: ATSKeywordImportance[];
  section_ranking: ATSSectionScore[];
  improvement_plan: ATSImprovementItem[];
  recruiter_take: string | null;
  methodology: string;
}

export interface PredictedQuestionItem {
  category: "hr" | "technical" | "behavioral";
  question: string;
  prep_tip: string;
}

export interface PredictQuestionsResponse {
  questions: PredictedQuestionItem[];
  error: boolean;
  message: string;
}

export interface HealthResponse {
  api: string;
  provider: string;
  model: string;
  ollama: string;
  model_loaded: boolean;
  detail?: string;
  storage: string;
}

export interface ApiErrorBody {
  detail?: string | { msg: string }[];
}
