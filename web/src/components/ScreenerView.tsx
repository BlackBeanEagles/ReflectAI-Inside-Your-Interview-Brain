// The résumé the way the screener read it.
//
// The ATS page used to report keyword match as a list of bars: "python
// 18%", "kubernetes 12%". Accurate, and hard to act on, because the
// question someone actually has is "which parts of MY résumé counted, and
// what is missing". This answers it on the document itself: every keyword
// the scorer matched is highlighted where it appears, the way a recruiter
// skims with a highlighter, and the ones it looked for and did not find
// are listed beside it, heaviest first.
//
// Only for pasted text. An uploaded PDF is parsed on the server and its
// text never comes back, so there is nothing faithful to draw -- in that
// case the missing list still renders and the document panel says why it
// is absent, rather than showing an approximation.

import { highlightSegments } from "@/lib/highlight";
import type { ATSKeywordItem } from "@/lib/types";

// The heaviest misses are the ones worth acting on; past a dozen the list
// stops being advice and becomes a wall. The count above still reports
// every keyword, so nothing is hidden from the total.
const MISSING_SHOWN = 12;

const labelOf = (k: ATSKeywordItem) => k.label || k.keyword;

export default function ScreenerView({
  text,
  matched,
  missing,
}: {
  /** The résumé exactly as it was scored, or null for an uploaded file. */
  text: string | null;
  matched: ATSKeywordItem[];
  missing: ATSKeywordItem[];
}) {
  // Highlight what the scorer actually matched in the résumé -- found_as,
  // which includes synonyms (posting: Postgres, résumé: PostgreSQL). The
  // normalised key is the fallback for older responses, and it is wrong
  // often enough ("redi") that it is only a fallback.
  const terms = matched.flatMap((k) => (k.found_as?.length ? k.found_as : [k.keyword]));
  const segments = text ? highlightSegments(text, terms) : [];
  const missingByWeight = [...missing].sort((a, b) => b.weight - a.weight);
  const shownMissing = missingByWeight.slice(0, MISSING_SHOWN);
  const hiddenMissing = missingByWeight.length - shownMissing.length;

  return (
    <section className="grid gap-5 md:grid-cols-[1fr_15rem]">
      <div className="min-w-0">
        <p className="ri-eyebrow mb-2">Your résumé, as the screener read it</p>
        {text ? (
          <div className="ri-ruled ri-ruled-margin max-h-[28rem] overflow-y-auto whitespace-pre-wrap py-1 pr-2 text-[13px] text-ri-text">
            {segments.map((s, i) =>
              s.match ? (
                <mark key={i} className="ri-highlight">
                  {s.text}
                </mark>
              ) : (
                <span key={i}>{s.text}</span>
              ),
            )}
          </div>
        ) : (
          <p className="text-sm text-ri-text-mute">
            Uploaded PDFs are read on the server, so the marked-up copy is only available for
            pasted text. The keywords it looked for are still listed here.
          </p>
        )}
        <p className="mt-2 text-xs text-ri-text-mute">
          {matched.length} of {matched.length + missing.length} keywords from the posting found.
        </p>
      </div>

      <div>
        <p className="ri-eyebrow mb-2">Looked for, not found</p>
        {missingByWeight.length === 0 ? (
          <p className="text-sm text-ri-text-mute">Nothing — every keyword it checked appears.</p>
        ) : (
          <>
            <ul className="flex flex-wrap gap-1.5">
              {shownMissing.map((k) => (
                // Dashed rather than filled: these are absences, so they are
                // drawn as an outline of something that is not there.
                <li
                  key={k.keyword}
                  className="rounded-full border border-dashed border-ri-border-strong px-2.5 py-0.5 text-xs text-ri-text-mute"
                >
                  {labelOf(k)}
                </li>
              ))}
            </ul>
            {hiddenMissing > 0 && (
              <p className="mt-2 text-xs text-ri-text-mute">
                and {hiddenMissing} lower-weighted {hiddenMissing === 1 ? "term" : "terms"}
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
