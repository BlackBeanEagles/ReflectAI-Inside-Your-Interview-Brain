// Split text into plain and matched segments for a set of keywords.
//
// Used to show a résumé the way the ATS screener read it: every keyword the
// scorer counted as a match is marked where it actually appears. That only
// works if the marking agrees with the matching, so the awkward cases are
// handled deliberately rather than left to a naive regex:
//
//  - Keywords are full of regex metacharacters (C++, Node.js, CI/CD, .NET),
//    so they are escaped.
//  - \b is wrong for them: it needs a word character on one side, and the
//    "+" in C++ is not one, so /\bC\+\+\b/ never matches "C++ developer".
//    Boundaries are "not a letter or digit" lookarounds instead.
//  - Overlapping keywords ("React" inside "React Native") are tried longest
//    first, so the longer phrase wins rather than being split.
//  - Matching is case-insensitive, like the scorer, but the original text
//    is returned untouched -- this marks the résumé, it does not rewrite it.

export type Segment = { text: string; match: boolean };

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\/-]/g, "\\$&");
}

export function highlightSegments(text: string, keywords: string[]): Segment[] {
  const terms = Array.from(
    new Set(keywords.map((k) => k.trim()).filter((k) => k.length > 0)),
  ).sort((a, b) => b.length - a.length);

  if (!text || terms.length === 0) return text ? [{ text, match: false }] : [];

  const pattern = new RegExp(
    // A two-word phrase can be split by a line break or two spaces in the
    // résumé, so the gap between its words matches any run of whitespace.
    `(?<![A-Za-z0-9])(${terms.map((t) => escapeRegex(t).replace(/\s+/g, "\\s+")).join("|")})(?![A-Za-z0-9])`,
    "gi",
  );

  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    const start = m.index ?? 0;
    if (start > last) out.push({ text: text.slice(last, start), match: false });
    out.push({ text: m[0], match: true });
    last = start + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), match: false });
  return out;
}
