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
    return <span className="inline-block w-2 h-2 rounded-full bg-ri-text-mute" />;
  }
  const ok = health?.api === "ok";
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${ok ? "bg-ri-good-line" : "bg-ri-stress"}`}
      title={ok ? `${health?.model} ready (${health?.provider})` : "Backend unreachable"}
    />
  );
}

export default function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-ri-border bg-ri-surface sticky top-0 z-20">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2">
            <span className="text-xl">🎯</span>
            <span className="font-extrabold text-lg tracking-tight">ReflectInterview</span>
            <StatusDot />
          </div>
          <div className="hidden md:flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    active
                      ? "text-ri-accent bg-ri-info-bg"
                      : "text-ri-text-mute hover:text-ri-text hover:bg-ri-surface-alt"
                  }`}
                >
                  <span className="mr-1">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </div>
          <div className="flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-2 text-sm">
                <span className="hidden sm:inline text-ri-text-mute">
                  {user.name || user.email}
                </span>
                <button
                  onClick={logout}
                  className="px-3 py-1.5 rounded-md border border-ri-border text-sm hover:bg-ri-surface-alt"
                >
                  Log out
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className="px-3 py-1.5 rounded-md text-sm font-medium hover:bg-ri-surface-alt"
                >
                  Log in
                </Link>
                <Link
                  href="/signup"
                  className="px-3 py-1.5 rounded-md text-sm font-medium bg-ri-accent text-white hover:opacity-90"
                >
                  Sign up
                </Link>
              </div>
            )}
          </div>
        </div>
        {/* Mobile nav row -- horizontally scrollable so it never wraps awkwardly */}
        <div className="md:hidden flex gap-1 overflow-x-auto pb-2 -mx-1 px-1">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`shrink-0 px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap ${
                  active ? "text-ri-accent bg-ri-info-bg" : "text-ri-text-mute bg-ri-surface-alt"
                }`}
              >
                <span className="mr-1">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </header>
  );
}
