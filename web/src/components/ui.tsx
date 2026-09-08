"use client";

// Small, shared presentational pieces used across pages -- kept in one file
// since none of these is large enough to warrant its own module yet.
//
// Motion note: every animation here is CSS-driven except the score count-up,
// which needs a value per frame. Nothing schedules work on a timer, and the
// global `prefers-reduced-motion` block in globals.css switches all of it off
// at once rather than each component checking for itself.

import { useEffect, useRef, useState } from "react";

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "var(--ri-text-mute)";
  if (score >= 7.5) return "var(--ri-good-line)";
  if (score >= 5) return "var(--ri-warn-line)";
  return "var(--ri-stress)";
}

/** Counts from 0 up to `target` over ~700ms on mount and whenever the target
 *  changes. Driven by rAF rather than an interval so it tracks the display's
 *  actual refresh rate, and it always lands exactly on `target` instead of
 *  wherever the last tick happened to fall. */
function useCountUp(target: number | null | undefined, duration = 700): number | null {
  const [value, setValue] = useState<number | null>(target ?? null);
  const frameRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (target == null) {
      // No value to animate to -- settle immediately, off the effect body so
      // this stays a state update from a callback rather than a render-phase one.
      const id = requestAnimationFrame(() => setValue(null));
      return () => cancelAnimationFrame(id);
    }

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      const id = requestAnimationFrame(() => setValue(target));
      return () => cancelAnimationFrame(id);
    }

    let start: number | null = null;
    const step = (now: number) => {
      if (start === null) start = now;
      const t = Math.min(1, (now - start) / duration);
      // easeOutCubic: fast off the mark, gentle landing.
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) frameRef.current = requestAnimationFrame(step);
      else setValue(target);
    };
    frameRef.current = requestAnimationFrame(step);

    return () => {
      if (frameRef.current !== undefined) cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration]);

  return value;
}

/** A score out of 10 as a ring that draws itself in, with the number
 *  counting up inside it. The ring makes a 6.2 and an 8.9 distinguishable
 *  at a glance across a row of panels, which a column of bare numerals
 *  never quite manages. */
export function ScorePanel({
  label,
  score,
  size = "md",
}: {
  label: string;
  score: number | null | undefined;
  size?: "sm" | "md";
}) {
  const shown = useCountUp(score);
  const color = scoreColor(score);

  const r = size === "sm" ? 20 : 26;
  const stroke = size === "sm" ? 4 : 5;
  const box = (r + stroke) * 2;
  const len = 2 * Math.PI * r;
  const pct = score != null ? Math.max(0, Math.min(1, score / 10)) : 0;
  const offset = len * (1 - pct);

  return (
    <div className="ri-lift flex-1 min-w-[104px] rounded-2xl border border-ri-border bg-ri-surface-alt/70 p-3 text-center backdrop-blur-sm">
      <div className="relative mx-auto" style={{ width: box, height: box }}>
        <svg width={box} height={box} viewBox={`0 0 ${box} ${box}`} className="-rotate-90">
          <circle
            cx={box / 2}
            cy={box / 2}
            r={r}
            fill="none"
            stroke="var(--ri-track)"
            strokeWidth={stroke}
          />
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
                } as React.CSSProperties
              }
            />
          )}
        </svg>
        <div
          className={`absolute inset-0 flex items-center justify-center font-extrabold tabular-nums ${
            size === "sm" ? "text-base" : "text-xl"
          }`}
          style={{ color }}
        >
          {shown != null ? shown.toFixed(1) : "N/A"}
        </div>
      </div>
      <div className="mt-1.5 text-[11px] font-semibold uppercase tracking-wide text-ri-text-mute">
        {label}
      </div>
    </div>
  );
}

/** Each round gets its own hue from the spectrum, so the badge, the question
 *  card's edge and any glow all shift together as the interview escalates
 *  HR -> technical -> stress. */
export const ROUND_ACCENT: Record<string, string> = {
  hr: "var(--ri-iris)",
  technical: "var(--ri-tech)",
  stress: "var(--ri-stress)",
};

export function RoundBadge({ round }: { round: string }) {
  const accent = ROUND_ACCENT[round] || ROUND_ACCENT.hr;
  return (
    <span
      className="ri-pop inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em]"
      style={{
        color: accent,
        borderColor: `color-mix(in srgb, ${accent} 45%, transparent)`,
        background: `color-mix(in srgb, ${accent} 12%, transparent)`,
        boxShadow: `0 0 18px color-mix(in srgb, ${accent} 22%, transparent)`,
      }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: accent, boxShadow: `0 0 8px ${accent}` }}
      />
      {round}
    </span>
  );
}

export function Card({
  children,
  className = "",
  glow = false,
  iridescent = false,
}: {
  children: React.ReactNode;
  className?: string;
  /** Draws the animated spectrum hairline along the card's top edge --
   *  reserve it for the one card that is the point of the page. */
  glow?: boolean;
  /** Wraps the whole card in a slowly panning spectrum ring. Stronger than
   *  `glow`; use it on at most one card per view. */
  iridescent?: boolean;
}) {
  // `iridescent` supersedes `glow` rather than stacking with it: both are
  // implemented as a ::before on this same element, so applying both would
  // merge into one pseudo-element and cascade the two rule sets together --
  // the top hairline would inherit the bloom's blur and vice versa. Passing
  // both is treated as asking for the stronger of the two.
  const edge = iridescent ? "ri-iridescent" : glow ? "ri-edge-glow" : "";
  return (
    <div className={`ri-glass rounded-2xl p-5 ${edge} ${className}`}>{children}</div>
  );
}

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
      className={`ri-sheen ri-focus relative rounded-xl px-4 py-2.5 font-semibold text-white
        transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0
        disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0
        bg-[linear-gradient(120deg,var(--ri-azure),var(--ri-indigo)_28%,var(--ri-violet)_52%,var(--ri-orchid)_74%,var(--ri-magenta))]
        bg-[length:220%_100%] bg-[position:0%_50%] hover:bg-[position:100%_50%]
        shadow-[0_4px_16px_color-mix(in_srgb,var(--ri-iris)_38%,transparent)]
        hover:shadow-[0_8px_28px_color-mix(in_srgb,var(--ri-violet)_48%,transparent)]
        disabled:shadow-none ${className}`}
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
      className={`ri-focus rounded-xl border border-ri-border bg-ri-surface/60 px-4 py-2.5 font-semibold
        backdrop-blur-sm transition-all duration-300
        hover:-translate-y-0.5 hover:border-ri-accent/50 hover:bg-ri-surface-alt
        active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-45
        disabled:hover:translate-y-0 ${className}`}
    >
      {children}
    </button>
  );
}

const FIELD_CLASS = `w-full rounded-xl border border-ri-border bg-ri-surface-mute/70 px-3.5 py-2.5 text-sm
  transition-all duration-200 placeholder:text-ri-text-mute/70
  focus:border-ri-accent focus:bg-ri-surface focus:outline-none
  focus:shadow-[0_0_0_4px_color-mix(in_srgb,var(--ri-accent)_16%,transparent)]`;

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
      {help && <span className="mt-1 block text-xs text-ri-text-mute">{help}</span>}
    </label>
  );
}

export function TextArea({
  label,
  value,
  onChange,
  placeholder,
  rows = 6,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className={`${FIELD_CLASS} resize-y font-mono leading-relaxed`}
      />
    </label>
  );
}

const ALERT_STYLES: Record<string, { cls: string; line: string; icon: string }> = {
  error: { cls: "bg-ri-warn-bg text-ri-warn-fg", line: "var(--ri-warn-line)", icon: "⚠️" },
  success: { cls: "bg-ri-good-bg text-ri-good-fg", line: "var(--ri-good-line)", icon: "✅" },
  info: { cls: "bg-ri-info-bg text-ri-info-fg", line: "var(--ri-info-line)", icon: "💡" },
};

export function Alert({
  kind,
  children,
}: {
  kind: "error" | "success" | "info";
  children: React.ReactNode;
}) {
  const s = ALERT_STYLES[kind];
  // Errors interrupt (role="alert", implicit aria-live="assertive") since a
  // screen reader user submitting a form needs to hear about a failure
  // immediately, the same way a sighted user sees it appear instantly.
  // Success/info use role="status" (polite) -- worth announcing, not urgent
  // enough to talk over whatever the user's currently doing.
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`ri-rise flex items-start gap-2.5 rounded-xl border-l-[3px] px-4 py-3 text-sm ${s.cls}`}
      style={{ borderLeftColor: s.line }}
    >
      <span aria-hidden className="mt-px shrink-0">
        {s.icon}
      </span>
      <span className="min-w-0">{children}</span>
    </div>
  );
}

/** Three drifting dots rather than a spinning ring. Model calls here take
 *  seconds, and a bouncing row reads as "thinking" where a spinner reads as
 *  "stuck". */
export function Spinner({ label }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2.5 text-sm text-ri-text-mute">
      <span className="flex items-end gap-1" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="ri-dot inline-block h-1.5 w-1.5 rounded-full"
            style={{
              background: [
                "var(--ri-azure)",
                "var(--ri-violet)",
                "var(--ri-magenta)",
              ][i],
            }}
          />
        ))}
      </span>
      {label}
    </div>
  );
}

/** Indeterminate bar for "something is happening, duration unknown". */
export function ProgressTrack() {
  return (
    <div
      className="h-1 w-full overflow-hidden rounded-full bg-ri-track"
      role="progressbar"
      aria-label="Loading"
    >
      <div className="ri-track-slide h-full w-1/4 rounded-full bg-[linear-gradient(90deg,var(--ri-azure),var(--ri-violet),var(--ri-magenta))]" />
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
  const accent = ROUND_ACCENT[round] || ROUND_ACCENT.hr;
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-ri-track"
      role="progressbar"
      aria-valuenow={current}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-label={`Question ${current} of ${total}`}
    >
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{
          width: `${pct}%`,
          background: `linear-gradient(90deg, color-mix(in srgb, ${accent} 55%, transparent), ${accent})`,
          boxShadow: `0 0 12px color-mix(in srgb, ${accent} 55%, transparent)`,
        }}
      />
    </div>
  );
}
