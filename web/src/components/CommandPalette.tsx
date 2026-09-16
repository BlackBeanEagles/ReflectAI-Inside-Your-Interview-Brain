"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Moon, Search, Sun } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { NAV_ITEMS } from "@/lib/nav-items";
import { useTheme } from "@/lib/theme";

type Command = {
  id: string;
  label: string;
  hint?: string;
  keywords: string;
  icon: LucideIcon;
  run: () => void;
};

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
  const { theme, toggle: toggleTheme } = useTheme();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  // Whatever had focus before the palette opened, so it can be handed back.
  const returnFocusRef = useRef<HTMLElement | null>(null);

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
    // The header's search button opens the palette through this event
    // rather than through shared state: the palette is mounted in the
    // layout beside Nav, not inside it, so there is no prop path between
    // them and lifting the open flag into a context would be three files
    // of plumbing for one boolean.
    function onOpenRequest() {
      setQuery("");
      setActive(0);
      setOpen(true);
    }

    document.addEventListener("keydown", onKey);
    document.addEventListener("ri:open-palette", onOpenRequest);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("ri:open-palette", onOpenRequest);
    };
  }, []);

  // Focus in on open, and back out on close.
  //
  // Without the restore, dismissing the palette left focus on <body>: a
  // keyboard user's next Tab started again from the top of the document,
  // which after a dismissal that changed nothing is a surprising place to
  // land. Storing the previously focused element is the only way to put
  // it back, since by the time we close it is long gone.
  useEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    return () => {
      returnFocusRef.current?.focus?.();
      returnFocusRef.current = null;
    };
  }, [open]);

  // A dialog with aria-modal="true" claims to contain focus, so it has to
  // actually do it -- otherwise Tab walks into the page behind, where a
  // screen reader has already been told nothing exists.
  useEffect(() => {
    if (!open) return;
    function onTab(e: KeyboardEvent) {
      if (e.key !== "Tab" || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'input, button, [href], [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const activeEl = document.activeElement;
      if (e.shiftKey && (activeEl === first || !dialogRef.current.contains(activeEl))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && activeEl === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onTab);
    return () => document.removeEventListener("keydown", onTab);
  }, [open]);

  // Hold the page still underneath. Scrolling the results list otherwise
  // scrolls the page behind it once the list hits its end, and the page is
  // left somewhere else entirely when the palette closes.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
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
        ref={dialogRef}
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
