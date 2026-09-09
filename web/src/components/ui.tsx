"use client";

// Small, shared presentational pieces used across pages -- kept in one file
// since none of these is large enough to warrant its own module yet.
//
// Motion note: every animation here is pure CSS. Nothing animates a rendered
// VALUE, deliberately -- a previous version counted the score up frame by
// frame with requestAnimationFrame, and rAF is throttled whenever the tab
// isn't painting, so the number could sit frozen at (observed) 1.5 while the
// real score was 8.0. A wrong number is far worse than no animation. The
// global `prefers-reduced-motion` block in globals.css switches the rest off
// at once rather than each component checking for itself.

import type { CSSProperties } from "react";

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "var(--ri-text-mute)";
  if (score >= 7.5) return "var(--ri-good-line)";
  if (score >= 5) return "var(--ri-warn-line)";
  return "var(--ri-stress)";
}

/** A score out of 10: the exact value in the middle, with a ring that sweeps
 *  to it on arrival. The ring is what makes a 6.2 and an 8.9 separable at a
 *  glance across a row of panels, which a row of bare numerals is not. */
export function ScorePanel({
  label,
  score,
  size = "md",
}: {
  label: string;
  score: number | null | undefined;
  size?: "sm" | "md";
}) {
  const color = scoreColor(score);

  const r = size === "sm" ? 19 : 24;
  const stroke = size === "sm" ? 3 : 3.5;
  const box = (r + stroke) * 2;
  const len = 2 * Math.PI * r;
  const pct = score != null ? Math.max(0, Math.min(1, score / 10)) : 0;
  const offset = len * (1 - pct);

  return (
    <div className="min-w-[104px] flex-1 rounded-ri-control border border-ri-border bg-ri-surface p-3 text-center transition-shadow duration-200 hover:shadow-[var(--ri-shadow-lift)]">
      <div className="relative mx-auto" style={{ width: box, height: box }}>
        <svg width={box} height={box} viewBox={`0 0 ${box} ${box}`} className="-rotate-90">
          <circle cx={box / 2} cy={box / 2} r={r} fill="none" stroke="var(--ri-track)" strokeWidth={stroke} />
          {score != null && (
            <circle
              className="ri-ring-draw"
              cx={box / 2}
              cy={box / 2}
              r={r}
              fill="none"
              stroke={color}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={len}
              style={
                {
                  "--ri-ring-len": len,
                  "--ri-ring-offset": offset,
                  strokeDashoffset: offset,
                } as CSSProperties
              }
            />
          )}
        </svg>
        <div
          className={`absolute inset-0 flex items-center justify-center font-semibold tabular-nums tracking-tight ${
            size === "sm" ? "text-sm" : "text-lg"
          }`}
          style={{ color }}
        >
          {score != null ? score.toFixed(1) : "–"}
        </div>
      </div>
      <div className="ri-eyebrow mt-2 truncate">{label}</div>
    </div>
  );
}

/** The three rounds warm as the interview escalates, so you can tell where
 *  you are without reading the label. */
export const ROUND_ACCENT: Record<string, string> = {
  hr: "var(--ri-hr)",
  technical: "var(--ri-tech)",
  stress: "var(--ri-stress)",
};

const ROUND_LABEL: Record<string, string> = {
  hr: "HR round",
  technical: "Technical round",
  stress: "Stress round",
};

export function RoundBadge({ round }: { round: string }) {
  const accent = ROUND_ACCENT[round] || ROUND_ACCENT.hr;
  return (
    <span
      className="inline-flex items-center gap-2 text-xs font-semibold"
      style={{ color: accent }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: accent }} />
      {ROUND_LABEL[round] || round}
    </span>
  );
}

export function Card({
  children,
  className = "",
  flush = false,
}: {
  children: React.ReactNode;
  className?: string;
  /** Drop the padding, for a card holding a full-bleed table, image or
   *  clickable header that should reach the card's edges. */
  flush?: boolean;
}) {
  // Padded by default. A previous version made callers wrap content in a
  // separate <CardBody>, which meant every card that forgot to became a
  // borderless-looking box with text jammed against its edge -- and eight
  // pages did exactly that. Defaults should be what most callers want.
  return (
    <div
      className={`rounded-ri-card border border-ri-border bg-ri-surface shadow-[var(--ri-shadow)] ${
        flush ? "" : "p-5"
      } ${className}`}
    >
      {children}
    </div>
  );
}

// active:scale is the cheapest honest affordance there is: a control that
// visibly responds to being pressed feels responsive even when the work behind
// it takes two seconds. transition covers transform too, so the release eases
// back rather than snapping.
const BTN_BASE =
  "ri-focus inline-flex items-center justify-center gap-2 rounded-ri-control px-4 text-sm font-medium " +
  "transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed " +
  "disabled:opacity-50 disabled:active:scale-100";

export function PrimaryButton({
  children,
  onClick,
  disabled,
  type = "button",
  className = "",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      // min-h-10 rather than vertical padding: buttons keep a consistent
      // 40px hit target whether their label wraps or not.
      className={`${BTN_BASE} min-h-10 bg-ri-accent py-2 text-white shadow-[var(--ri-shadow)] hover:bg-[var(--ri-accent-hover)] hover:shadow-[var(--ri-shadow-lift)] disabled:shadow-none ${className}`}
    >
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  onClick,
  disabled,
  className = "",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`${BTN_BASE} min-h-10 border border-ri-border bg-ri-surface py-2 text-ri-text hover:border-ri-border-strong hover:bg-ri-surface-alt ${className}`}
    >
      {children}
    </button>
  );
}

const FIELD_CLASS =
  "w-full rounded-ri-control border border-ri-border bg-ri-surface px-3 py-2 text-sm text-ri-text " +
  "transition-colors placeholder:text-ri-text-mute/60 focus:border-ri-accent focus:outline-none " +
  "focus:ring-2 focus:ring-ri-accent/25";

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  help,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  help?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={FIELD_CLASS}
      />
      {help && <span className="mt-1.5 block text-xs text-ri-text-mute">{help}</span>}
    </label>
  );
}

export function TextArea({
  label,
  value,
  onChange,
  placeholder,
  rows = 6,
  onSubmit,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  /** Fired on Ctrl/Cmd+Enter. Plain Enter still inserts a newline -- these
   *  are multi-paragraph answers, so Enter-to-submit would be hostile. */
  onSubmit?: () => void;
  hint?: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={
          onSubmit
            ? (e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  onSubmit();
                }
              }
            : undefined
        }
        placeholder={placeholder}
        rows={rows}
        className={`${FIELD_CLASS} resize-y leading-relaxed`}
      />
      {hint && <span className="mt-1.5 block text-xs text-ri-text-mute">{hint}</span>}
    </label>
  );
}

const ALERT_STYLES: Record<string, string> = {
  error: "border-ri-warn-line/35 bg-ri-warn-bg text-ri-warn-fg",
  success: "border-ri-good-line/35 bg-ri-good-bg text-ri-good-fg",
  info: "border-ri-info-line/30 bg-ri-info-bg text-ri-info-fg",
};

export function Alert({
  kind,
  children,
}: {
  kind: "error" | "success" | "info";
  children: React.ReactNode;
}) {
  // Errors interrupt (role="alert", implicit aria-live="assertive") since a
  // screen reader user submitting a form needs to hear about a failure
  // immediately, the same way a sighted user sees it appear instantly.
  // Success/info use role="status" (polite) -- worth announcing, not urgent
  // enough to talk over whatever the user's currently doing.
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`rounded-ri-control border px-3.5 py-2.5 text-sm ${ALERT_STYLES[kind]}`}
    >
      {children}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2.5 text-sm text-ri-text-mute">
      <span
        aria-hidden
        className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-ri-border border-t-ri-accent"
      />
      {label}
    </div>
  );
}

/** "The interviewer is considering your answer." Distinct from <Spinner>,
 *  which means "a request is in flight" -- the two read differently even at
 *  the same latency, and in a product built to feel like a conversation that
 *  difference is worth carrying in the UI. */
export function Thinking({ label = "Considering your answer" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2.5 text-sm text-ri-text-mute">
      <span className="ri-think flex items-center gap-1" aria-hidden>
        <span className="h-1.5 w-1.5 rounded-full bg-ri-text-mute" />
        <span className="h-1.5 w-1.5 rounded-full bg-ri-text-mute" />
        <span className="h-1.5 w-1.5 rounded-full bg-ri-text-mute" />
      </span>
      {label}
    </div>
  );
}

/** Indeterminate bar for "something is happening, duration unknown". */
export function ProgressTrack() {
  return (
    <div className="h-0.5 w-full overflow-hidden rounded-full bg-ri-track" role="progressbar" aria-label="Loading">
      <div className="ri-indeterminate h-full w-1/4 rounded-full bg-ri-accent" />
    </div>
  );
}

/** Determinate progress through the interview, tinted by the current round
 *  so the bar itself carries the escalation. */
export function RoundProgress({
  current,
  total,
  round,
}: {
  current: number;
  total: number;
  round: string;
}) {
  const pct = Math.max(0, Math.min(100, (current / total) * 100));
  return (
    <div
      className="h-0.5 w-full overflow-hidden rounded-full bg-ri-track"
      role="progressbar"
      aria-valuenow={current}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-label={`Question ${current} of ${total}`}
    >
      <div
        className="h-full rounded-full transition-[width] duration-500 ease-out"
        style={{ width: `${pct}%`, background: ROUND_ACCENT[round] || ROUND_ACCENT.hr }}
      />
    </div>
  );
}
