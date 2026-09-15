"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Moon, Search, Sun } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { NAV_ITEMS } from "@/lib/nav-items";

const THEME_KEY = "reflectinterview_theme";

type Command = {
  id: string;
  label: string;
  hint?: string;
  keywords: string;
  icon: LucideIcon;
  run: () => void;
};

/** Read the stored theme. Wrapped because localStorage throws outright in a
 *  private window rather than returning null. */
function storedTheme(): "light" | "dark" | null {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "dark" || v === "light" ? v : null;
  } catch {
    return null;
  }
}

function applyTheme(theme: "light" | "dark") {
  // Dark is opt-in via the data-theme attribute, deliberately NOT
  // prefers-color-scheme: the app was following the OS setting and handing
  // people a dark interview room they never asked for.
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* Private window: the theme just doesn't persist. Not worth surfacing. */
  }
}

/**
 * Cmd/Ctrl+K to jump anywhere.
 *
 * The app is five pages deep with a persistent header, so this is not
 * about reachability -- everything here is two clicks away already. It is
 * about not losing your place: the header is above the fold on desktop but
 * scrolls away on mobile, and mid-interview the thing people want is
 * usually "my last report", not "the History tab".
 *
 * Deliberately small: navigation plus the theme switch. A palette that
 * lists commands you could not otherwise perform is a second, worse menu.
 */
export default function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Restore the stored theme on first paint. A microtask, not rAF:
  // requestAnimationFrame does not fire while a tab isn't painting, so a
  // restore scheduled there silently never runs on a backgrounded tab.
  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(() => {
      if (cancelled) return;
      const saved = storedTheme();
      if (saved) {
        setTheme(saved);
        applyTheme(saved);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      applyTheme(next);
      return next;
    });
  }, []);

  const commands = useMemo<Command[]>(() => {
    const nav = NAV_ITEMS.map((item) => ({
      id: `nav:${item.href}`,
      label: item.label,
      hint: "Go to",
      keywords: `${item.label} ${item.keywords ?? ""}`,
      icon: item.icon,
      run: () => router.push(item.href),
    }));
    return [
      ...nav,
      {
        id: "theme",
        label: theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
        keywords: "theme dark light appearance contrast night",
        icon: theme === "dark" ? Sun : Moon,
        run: toggleTheme,
      },
    ];
  }, [router, theme, toggleTheme]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.keywords.toLowerCase().includes(q));
  }, [commands, query]);

  // Open/close. Listens on keydown at the document so it works from
  // anywhere, including while a textarea has focus mid-answer.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
        setQuery("");
        setActive(0);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  // Keep the highlighted row in view when arrowing past the visible edge.
  useEffect(() => {
    listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  function choose(cmd: Command | undefined) {
    if (!cmd) return;
    setOpen(false);
    cmd.run();
  }

  function onInputKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (results.length ? (i + 1) % results.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (results.length ? (i - 1 + results.length) % results.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(results[active]);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-[rgba(20,18,15,0.32)] px-4 pt-[12vh] backdrop-blur-[2px]"
      onClick={() => setOpen(false)}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
        className="ri-enter w-full max-w-lg overflow-hidden rounded-[var(--ri-radius-card)] border border-ri-border bg-ri-surface shadow-xl"
      >
        <div className="flex items-center gap-2 border-b border-ri-border px-3.5 py-3">
          <Search size={15} strokeWidth={1.75} className="shrink-0 text-ri-text-mute" aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onInputKey}
            placeholder="Jump to a page…"
            aria-label="Search commands"
            className="w-full bg-transparent text-sm text-ri-text outline-none placeholder:text-ri-text-mute"
          />
          <kbd className="hidden shrink-0 rounded border border-ri-border px-1.5 py-0.5 text-[10px] text-ri-text-mute sm:block">
            Esc
          </kbd>
        </div>

        {results.length === 0 ? (
          <p className="px-3.5 py-6 text-center text-sm text-ri-text-mute">
            Nothing matches “{query}”.
          </p>
        ) : (
          <ul ref={listRef} className="max-h-[50vh] overflow-y-auto py-1.5">
            {results.map((cmd, i) => {
              const Icon = cmd.icon;
              const isActive = i === active;
              return (
                <li key={cmd.id}>
                  <button
                    type="button"
                    data-active={isActive}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => choose(cmd)}
                    className={`flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm transition-colors ${
                      isActive ? "bg-ri-accent-soft text-ri-accent" : "text-ri-text"
                    }`}
                  >
                    <Icon size={15} strokeWidth={1.75} className="shrink-0" aria-hidden />
                    <span className="min-w-0 truncate">{cmd.label}</span>
                    {cmd.hint && (
                      <span className="ml-auto shrink-0 text-xs text-ri-text-mute">{cmd.hint}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
