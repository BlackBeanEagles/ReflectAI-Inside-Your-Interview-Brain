// Small, shared presentational pieces used across pages -- kept in one file
// since none of these is large enough to warrant its own module yet.

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "var(--ri-text-mute)";
  if (score >= 7.5) return "var(--ri-good-line)";
  if (score >= 5) return "var(--ri-warn-line)";
  return "var(--ri-stress)";
}

export function ScorePanel({ label, score }: { label: string; score: number | null | undefined }) {
  return (
    <div className="flex-1 min-w-[100px] bg-ri-surface-alt border border-ri-border rounded-xl p-3 text-center">
      <div className="text-3xl font-extrabold" style={{ color: scoreColor(score) }}>
        {score != null ? score.toFixed(1) : "N/A"}
      </div>
      <div className="text-xs text-ri-text-mute uppercase tracking-wide font-semibold mt-1">
        {label}
      </div>
    </div>
  );
}

export function RoundBadge({ round }: { round: string }) {
  const styles: Record<string, string> = {
    hr: "bg-ri-info-bg text-ri-info-fg border-ri-info-line",
    technical: "bg-ri-warn-bg text-ri-warn-fg border-ri-warn-line",
    stress: "bg-ri-purple-bg text-ri-stress border-ri-stress",
  };
  const cls = styles[round] || styles.hr;
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${cls}`}>
      {round}
    </span>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-ri-surface border border-ri-border rounded-xl p-5 ${className}`}>
      {children}
    </div>
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
      className={`px-4 py-2.5 rounded-lg font-semibold text-white bg-ri-accent hover:opacity-90
        disabled:opacity-50 disabled:cursor-not-allowed transition-all
        hover:-translate-y-0.5 active:translate-y-0 ${className}`}
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
      className={`px-4 py-2.5 rounded-lg font-semibold border border-ri-border
        hover:bg-ri-surface-alt disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${className}`}
    >
      {children}
    </button>
  );
}

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
      <span className="block text-sm font-medium mb-1.5">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2.5 rounded-lg border border-ri-border bg-ri-surface-mute
          focus:outline-none focus:ring-2 focus:ring-ri-accent text-sm"
      />
      {help && <span className="block text-xs text-ri-text-mute mt-1">{help}</span>}
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
      <span className="block text-sm font-medium mb-1.5">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full px-3 py-2.5 rounded-lg border border-ri-border bg-ri-surface-mute
          focus:outline-none focus:ring-2 focus:ring-ri-accent text-sm font-mono"
      />
    </label>
  );
}

export function Alert({ kind, children }: { kind: "error" | "success" | "info"; children: React.ReactNode }) {
  const styles: Record<string, string> = {
    error: "bg-ri-warn-bg text-ri-warn-fg border-ri-warn-line",
    success: "bg-ri-good-bg text-ri-good-fg border-ri-good-line",
    info: "bg-ri-info-bg text-ri-info-fg border-ri-info-line",
  };
  return (
    <div className={`px-4 py-3 rounded-lg border text-sm ${styles[kind]}`}>{children}</div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ri-text-mute">
      <span className="inline-block w-4 h-4 border-2 border-ri-accent border-t-transparent rounded-full animate-spin" />
      {label}
    </div>
  );
}
