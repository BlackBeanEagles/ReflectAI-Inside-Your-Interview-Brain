"use client";

// How long your answer would take to say out loud.
//
// This app scores communication and structure, but only after you have
// already given the answer -- and the single most common way a real
// interview answer goes wrong is length. Too short reads as no evidence;
// too long and the interviewer stops following somewhere in the middle
// and remembers only that you rambled. Neither is visible while typing,
// and neither is something the score afterwards can help you fix in the
// moment.
//
// It measures spoken time rather than characters, because that is the
// constraint an interview actually has. 130 words per minute is the
// usual figure for measured speech under mild pressure -- people speak
// faster when nervous, so this errs toward flattering, which is the safe
// direction for a warning.
//
// Deliberately advisory. There is no gate, no colour-coded failure, and
// the bands are wide: plenty of excellent answers are two words long
// ("no, and here is why") and plenty of good ones run three minutes. It
// is a mirror, not a rule.

const WORDS_PER_MINUTE = 130;

// Roughly 25 seconds and 100 seconds of speech.
const SHORT_WORDS = 55;
const LONG_WORDS = 215;

function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

function spokenSeconds(words: number): number {
  return Math.round((words / WORDS_PER_MINUTE) * 60);
}

function describe(words: number): { label: string; tone: string; fill: number } {
  const seconds = spokenSeconds(words);
  const readable =
    seconds < 60 ? `about ${seconds}s spoken` : `about ${Math.round(seconds / 60)} min spoken`;

  if (words < SHORT_WORDS) {
    return {
      label: `${readable} — room for a specific example`,
      tone: "var(--ri-text-mute)",
      fill: Math.min(words / SHORT_WORDS, 1) * 0.33,
    };
  }
  if (words <= LONG_WORDS) {
    return {
      label: `${readable} — a good length to say out loud`,
      tone: "var(--ri-good-line)",
      fill: 0.33 + ((words - SHORT_WORDS) / (LONG_WORDS - SHORT_WORDS)) * 0.42,
    };
  }
  return {
    label: `${readable} — long enough that an interviewer may start skimming`,
    tone: "var(--ri-warn-line)",
    // Past the band the bar keeps creeping but never fills, so there is
    // no "completed" feeling attached to overrunning.
    fill: Math.min(0.75 + (words - LONG_WORDS) / 600, 0.97),
  };
}

export default function AnswerPacing({ text }: { text: string }) {
  const words = countWords(text);

  // Nothing at all until there is something to measure. A meter sitting at
  // zero under an empty box is an instruction to perform for it.
  if (words === 0) return null;

  const { label, tone, fill } = describe(words);

  return (
    <div className="flex items-center gap-2.5">
      <div
        className="h-0.5 w-20 shrink-0 overflow-hidden rounded-full bg-ri-track"
        // The bar is decoration; the sentence beside it carries the
        // meaning, so screen readers get that and not a percentage.
        aria-hidden
      >
        <div
          className="h-full rounded-full transition-[width,background-color] duration-300 ease-out"
          style={{ width: `${fill * 100}%`, background: tone }}
        />
      </div>
      {/* Not a live region: this changes on every keystroke, and
          announcing it would talk over someone as they type. */}
      <span className="text-[11px] text-ri-text-mute">
        {words} {words === 1 ? "word" : "words"}, {label}
      </span>
    </div>
  );
}
