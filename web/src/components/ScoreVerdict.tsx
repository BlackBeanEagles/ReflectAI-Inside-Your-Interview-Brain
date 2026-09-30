"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";

import * as api from "@/lib/api";

/** "Was this score fair?" -- one question, asked once per answer.
 *
 *  The scores come out of a language model and are sometimes wrong in ways
 *  only the person who wrote the answer can see. Without somewhere to say
 *  so, a bad score is just a thing the user quietly stops believing, and
 *  nothing about it reaches anyone who could fix it.
 *
 *  It is placed under the scores rather than above them -- it is a reaction
 *  to a number, so it cannot come first -- and it never blocks: the thanks
 *  render on click, before the request settles, and a failed request is
 *  swallowed. Losing a rating is not worth interrupting an interview for.
 *
 *  "Unfair" opens an optional one-line box, because why it was unfair is
 *  the only part of this signal anyone can act on. */
export default function ScoreVerdict({
  sessionId,
  question,
  round,
  score,
  token,
}: {
  sessionId: string | null;
  question: string | null;
  round: string;
  score: number;
  token: string | null;
}) {
  const [verdict, setVerdict] = useState<"fair" | "unfair" | null>(null);
  const [note, setNote] = useState("");
  const [noteSent, setNoteSent] = useState(false);

  // Exactly one request per answer, ever.
  //
  // The first version posted on the "off the mark" click and posted AGAIN
  // when a note was added, so every complaint that bothered to explain
  // itself was counted twice -- in precisely the number this feature
  // exists to produce. Now "unfair" only opens the note box, and the one
  // request goes out when the note is submitted.
  //
  // The cost of deferring is a verdict that could be lost if the user
  // moves on without touching the box, so the pending verdict is flushed
  // on unmount too. The ref is what both paths check: state would be stale
  // inside the unmount cleanup, and a second send is the bug being fixed.
  const sentRef = useRef(false);
  const pendingRef = useRef<"fair" | "unfair" | null>(null);
  const noteRef = useRef("");

  const post = useCallback(
    (v: "fair" | "unfair", withNote?: string) => {
      if (sentRef.current || !sessionId) return;
      sentRef.current = true;
      api
        .sendAnswerFeedback(
          {
            session_id: sessionId,
            verdict: v,
            question: question ?? undefined,
            round_type: round,
            final_score: score,
            note: withNote?.trim() || undefined,
          },
          token,
        )
        .catch(() => {
          /* Best-effort. A rating is not worth an error banner mid-interview. */
        });
    },
    [sessionId, question, round, score, token],
  );

  // Flush a verdict the user chose but never submitted a note for -- they
  // hit "Next question" instead, which unmounts this.
  useEffect(() => {
    return () => {
      if (pendingRef.current) post(pendingRef.current, noteRef.current);
    };
  }, [post]);

  function choose(v: "fair" | "unfair") {
    setVerdict(v);
    // "Fair" has nothing to add, so it goes immediately. "Unfair" waits
    // for the note box, and the unmount flush covers it if none comes.
    if (v === "fair") post(v);
    else pendingRef.current = v;
  }

  if (verdict === null) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-xs text-ri-text-mute">
        <span>Was this score fair?</span>
        <button
          type="button"
          onClick={() => choose("fair")}
          className="ri-verdict-chip"
        >
          <ThumbsUp size={13} strokeWidth={1.75} aria-hidden /> Fair
        </button>
        <button
          type="button"
          onClick={() => choose("unfair")}
          className="ri-verdict-chip"
        >
          <ThumbsDown size={13} strokeWidth={1.75} aria-hidden /> Off the mark
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2 text-xs text-ri-text-mute" aria-live="polite">
      <p>Thanks — noted.</p>
      {verdict === "unfair" && !noteSent && (
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            value={note}
            maxLength={500}
            onChange={(e) => {
              setNote(e.target.value);
              noteRef.current = e.target.value;
            }}
            placeholder="What did it miss? (optional)"
            className="ri-focus flex-1 rounded-[var(--ri-radius-control)] border border-ri-border bg-ri-surface px-2.5 py-1.5 text-xs text-ri-text outline-none"
          />
          <button
            type="button"
            className="ri-verdict-chip shrink-0"
            onClick={() => {
              pendingRef.current = null;
              post("unfair", note);
              setNoteSent(true);
            }}
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}
