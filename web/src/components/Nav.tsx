"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useHealth } from "@/lib/hooks";

const NAV_ITEMS = [
  { href: "/", label: "Interview Session", icon: "🎯" },
  { href: "/resume", label: "Resume Analysis", icon: "📄" },
  { href: "/ats", label: "ATS Score", icon: "✅" },
  { href: "/predict", label: "Predicted Questions", icon: "🔮" },
  { href: "/history", label: "History", icon: "📊" },
];

function StatusDot() {
  const { health, checked } = useHealth();

  if (!checked) {
    return (
      <span
        role="status"
        aria-label="Checking backend status…"
        className="inline-block h-2 w-2 shrink-0 rounded-full bg-ri-text-mute/50"
      />
    );
  }

  const ok = health?.api === "ok";
  const text = ok ? `${health?.model} ready (${health?.provider})` : "Backend unreachable";
  const color = ok ? "var(--ri-good-line)" : "var(--ri-stress)";

  // `title` alone (a mouse-hover tooltip) isn't reliably exposed to screen
  // readers and doesn't exist on touch devices -- aria-label carries the
  // same text so the status is actually announced, not just visible as a
  // colored dot. The halo is decorative reinforcement of the same signal.
  return (
    <span role="status" aria-label={text} title={text} className="relative flex h-2 w-2 shrink-0">
      {ok && (
        <span
          aria-hidden
          className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
          style={{ background: color, animationDuration: "2.4s" }}
        />
      )}
      <span
        className="relative inline-flex h-2 w-2 rounded-full"
        style={{ background: color, boxShadow: `0 0 8px ${color}` }}
      />
    </span>
  );
}

export default function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-20 border-b border-ri-border/60 bg-[var(--ri-glass)] backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between gap-4">
          {/* Shrinkable below md, fixed at md and up. At 375px the logo +
              wordmark + auth buttons come out ~1px wider than the viewport, and
              a group that refuses to shrink gives the whole page a horizontal
              scrollbar; letting the wordmark truncate absorbs that. From md up
              the row has room, so it must NOT shrink -- otherwise flex trims
              the wordmark to "ReflectInte…" on a perfectly wide screen. */}
          <Link
            href="/"
            className="ri-focus group flex min-w-0 items-center gap-2.5 rounded-lg md:shrink-0"
          >
            {/* Gradient tile instead of a bare emoji -- gives the wordmark
                something to sit against and ties the header to the aurora. */}
            <span
              aria-hidden
              className="flex h-8 w-8 items-center justify-center rounded-xl text-base
                bg-[linear-gradient(135deg,var(--ri-iris),var(--ri-violet)_60%,var(--ri-magenta))]
                shadow-[0_3px_14px_color-mix(in_srgb,var(--ri-violet)_45%,transparent)]
                transition-transform duration-300 group-hover:scale-105 group-hover:rotate-6"
            >
              🎯
            </span>
            <span className="truncate text-[17px] font-extrabold tracking-tight">
              ReflectInterview
            </span>
            <StatusDot />
          </Link>

          <nav className="hidden items-center gap-0.5 md:flex">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`ri-focus relative rounded-lg px-3 py-2 text-sm font-medium transition-all duration-300 ${
                    active
                      ? "text-ri-accent"
                      : "text-ri-text-mute hover:-translate-y-px hover:text-ri-text"
                  }`}
                >
                  {active && (
                    <span
                      aria-hidden
                      className="absolute inset-0 rounded-lg border border-ri-accent/25
                        bg-[color-mix(in_srgb,var(--ri-accent)_12%,transparent)]
                        shadow-[0_0_18px_color-mix(in_srgb,var(--ri-accent)_22%,transparent)]"
                    />
                  )}
                  <span className="relative">
                    <span className="mr-1">{item.icon}</span>
                    {item.label}
                  </span>
                </Link>
              );
            })}
          </nav>

          <div className="flex shrink-0 items-center gap-3">
            {user ? (
              <div className="flex items-center gap-2 text-sm">
                <span className="hidden max-w-[160px] truncate text-ri-text-mute sm:inline">
                  {user.name || user.email}
                </span>
                <button
                  onClick={logout}
                  className="ri-focus rounded-lg border border-ri-border px-3 py-1.5 text-sm
                    transition-colors hover:border-ri-stress/50 hover:text-ri-stress"
                >
                  Log out
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className="ri-focus rounded-lg px-3 py-1.5 text-sm font-medium text-ri-text-mute
                    transition-colors hover:text-ri-text"
                >
                  Log in
                </Link>
                <Link
                  href="/signup"
                  className="ri-sheen ri-focus rounded-lg px-3.5 py-1.5 text-sm font-semibold text-white
                    bg-[linear-gradient(120deg,var(--ri-iris),var(--ri-violet))]
                    shadow-[0_3px_14px_color-mix(in_srgb,var(--ri-iris)_40%,transparent)]
                    transition-transform duration-300 hover:-translate-y-0.5"
                >
                  Sign up
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Mobile nav row -- horizontally scrollable so it never wraps awkwardly */}
        <nav className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-2 md:hidden">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`ri-focus shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? "border border-ri-accent/30 bg-[color-mix(in_srgb,var(--ri-accent)_14%,transparent)] text-ri-accent"
                    : "border border-ri-border bg-ri-surface-alt/60 text-ri-text-mute"
                }`}
              >
                <span className="mr-1">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
