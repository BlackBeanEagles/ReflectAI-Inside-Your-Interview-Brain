"use client";

// Predicted questions as something to work through, not something to read.
//
// The page calls itself a study tool, but it rendered a list you read once
// and closed: nothing to track which questions you had actually rehearsed,
// so coming back the next day meant re-reading all of them to remember.
// Now each one can be ticked off as practised, and the tick is kept on
// this device.
//
// Keyed by the question's text rather than its position, so a tick
// survives regenerating the list -- the generator often produces some of
// the same questions again, and those should arrive already done.

import { useId, useState } from "react";

import * as storage from "@/lib/safe-storage";
import type { PredictedQuestionItem } from "@/lib/types";

const KEY = "reflectinterview_prep_practised";
// Enough for months of use; stops the stored list growing forever.
const MAX_REMEMBERED = 400;

const keyFor = (q: string) => q.trim().toLowerCase();

const CATEGORY_LABEL: Record<string, string> = {
  technical: "Technical",
  hr: "HR",
  behavioral: "Behavioural",
};

export default function PrepChecklist({ questions }: { questions: PredictedQuestionItem[] }) {
  // Lazy initial read. This component only mounts once questions have come
  // back from the API, which is always on the client, so reading storage
  // here cannot mismatch server-rendered markup.
  const idBase = useId();
  const [done, setDone] = useState<Set<string>>(
    () => new Set(storage.readJson<string[]>(KEY) ?? []),
  );

  function toggle(question: string) {
    setDone((prev) => {
      const next = new Set(prev);
      const k = keyFor(question);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      storage.writeJson(KEY, [...next].slice(-MAX_REMEMBERED));
      return next;
    });
  }

  const practised = questions.filter((q) => done.has(keyFor(q.question))).length;
  const grouped = (["technical", "hr", "behavioral"] as const)
    .map((cat) => ({ cat, items: questions.filter((q) => q.category === cat) }))
    .filter((g) => g.items.length > 0);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-ri-track" aria-hidden>
          <div
            className="h-full rounded-full bg-ri-good-line transition-[width] duration-300"
            style={{ width: `${questions.length ? (practised / questions.length) * 100 : 0}%` }}
          />
        </div>
        <span className="shrink-0 text-xs tabular-nums text-ri-text-mute">
          {practised} of {questions.length} practised
        </span>
      </div>

      {grouped.map(({ cat, items }) => (
        <div key={cat}>
          <h3 className="mb-2 text-sm font-bold">{CATEGORY_LABEL[cat]}</h3>
          <ul className="space-y-1.5">
            {items.map((q, i) => {
              const isDone = done.has(keyFor(q.question));
              // The wrapping label makes the whole row the tap target, but
              // its text would also become the checkbox's accessible name
              // -- question AND tip, read out in full on every row. The
              // question is the name; the tip is the description.
              const qId = `${idBase}-${cat}-${i}-q`;
              const tipId = `${idBase}-${cat}-${i}-tip`;
              return (
                <li key={q.question}>
                  {/* The whole row is the label, so the tap target is the
                      question, not a 16px box beside it. */}
                  <label
                    className={`flex cursor-pointer gap-3 rounded-[var(--ri-radius-control)] border px-3 py-2.5 transition-colors ${
                      isDone
                        ? "border-ri-border bg-ri-surface-alt"
                        : "border-ri-border bg-ri-surface hover:border-ri-border-strong"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isDone}
                      onChange={() => toggle(q.question)}
                      aria-labelledby={qId}
                      aria-describedby={tipId}
                      className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--ri-good-line)]"
                    />
                    <span className="min-w-0">
                      {/* Dimmed, not struck through: a strike reads as
                          "wrong" or "removed", and a practised question is
                          neither -- it is still worth a second run. */}
                      <span
                        id={qId}
                        className={`block text-sm font-medium transition-opacity ${
                          isDone ? "opacity-60" : ""
                        }`}
                      >
                        {q.question}
                      </span>
                      <span id={tipId} className="mt-1 block text-xs text-ri-text-mute">
                        {q.prep_tip}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
