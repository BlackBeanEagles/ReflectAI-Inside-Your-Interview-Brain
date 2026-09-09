"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, FileText, ListChecks, MessagesSquare, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useHealth } from "@/lib/hooks";

// Real icons rather than emoji. Emoji render as a different typeface on every
// platform, can't inherit colour or stroke weight, and sit on their own
// baseline -- so a row of them never optically aligns with the labels beside
// them. lucide-react was already a dependency and previously went unused.
const NAV_ITEMS = [
  { href: "/", label: "Interview", icon: MessagesSquare },
  { href: "/resume", label: "Resume", icon: FileText },
  { href: "/ats", label: "ATS Score", icon: ListChecks },
  { href: "/predict", label: "Questions", icon: Sparkles },
  { href: "/history", label: "History", icon: BarChart3 },
];

function StatusDot() {
  const { health, checked } = useHealth();

  if (!checked) {
    return <span role="status" aria-label="Checking backend status…" className="h-1.5 w-1.5 shrink-0 rounded-full bg-ri-border-strong" />;
  }

  const ok = health?.api === "ok";
  const text = ok ? `${health?.model} ready (${health?.provider})` : "Backend unreachable";

  // `title` alone (a mouse-hover tooltip) isn't reliably exposed to screen
  // readers and doesn't exist on touch devices -- aria-label carries the same
  // text so the status is announced, not just visible as a coloured dot.
  return (
    <span
      role="status"
      aria-label={text}
      title={text}
      className="h-1.5 w-1.5 shrink-0 rounded-full"
      style={{ background: ok ? "var(--ri-good-line)" : "var(--ri-stress)" }}
    />
  );
}

export default function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  // Translucent rather than opaque: the page texture and wash stay visible
  // through the bar, so it reads as part of the same sheet instead of a white
  // strip laid on top of it.
  return (
    <header className="sticky top-0 z-20 border-b border-ri-border bg-[color-mix(in_srgb,var(--ri-surface)_82%,transparent)] backdrop-blur-md">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <div className="flex h-14 items-center justify-between gap-4">
          <Link href="/" className="ri-focus flex min-w-0 items-center gap-2 md:shrink-0">
            <span className="ri-title truncate text-[15px]">ReflectInterview</span>
            <StatusDot />
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`ri-focus flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm transition-colors ${
                    active
                      ? "bg-ri-accent-soft font-medium text-ri-accent"
                      : "text-ri-text-mute hover:bg-ri-surface-alt hover:text-ri-text"
                  }`}
                >
                  <Icon size={15} strokeWidth={1.75} aria-hidden />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="flex shrink-0 items-center gap-2 text-sm">
            {user ? (
              <>
                {/* The account page is where deletion lives, so it has to be
                    reachable in a click -- Play requires an in-app path to it,
                    and burying it would fail that as surely as not having it. */}
                <Link
                  href="/account"
                  className="ri-focus hidden max-w-[150px] truncate rounded-md px-2.5 py-1.5 text-ri-text-mute transition-colors hover:text-ri-text sm:inline-block"
                >
                  {user.name || user.email}
                </Link>
                <button
                  onClick={logout}
                  className="ri-focus rounded-md px-2.5 py-1.5 text-ri-text-mute transition-colors hover:text-ri-text"
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="ri-focus rounded-md px-2.5 py-1.5 text-ri-text-mute transition-colors hover:text-ri-text"
                >
                  Log in
                </Link>
                <Link
                  href="/signup"
                  className="ri-focus rounded-md bg-ri-accent px-3 py-1.5 font-medium text-white transition-colors hover:bg-[var(--ri-accent-hover)]"
                >
                  Sign up
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Mobile nav -- horizontally scrollable so it never wraps awkwardly */}
        <nav className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-2 md:hidden">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`ri-focus flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
                  active ? "bg-ri-accent-soft font-medium text-ri-accent" : "text-ri-text-mute"
                }`}
              >
                <Icon size={14} strokeWidth={1.75} aria-hidden />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
