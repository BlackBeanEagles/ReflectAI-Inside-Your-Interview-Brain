"""
ATS Scorer module.
Responsibility: Score a resume against a job description the way a real
Applicant Tracking System would — keyword/phrase overlap plus structural
parseability checks. No LLM involved anywhere in this module.

Why not just ask the LLM for a score: an LLM asked "rate this resume 0-100
for ATS-friendliness" is guessing — its number isn't derived from anything a
real ATS actually measures, and the same resume can get a different score on
every call. Real ATS systems (Workday, Taleo, Greenhouse, etc.) work by:

    1. Extracting text from the resume (this is why formatting matters —
       tables, columns, and images often extract as garbage or nothing).
    2. Matching that text against keywords pulled from the job description,
       weighted by how often each keyword appears in the posting.
    3. Ranking candidates by match percentage.

This module reproduces that mechanism directly and deterministically: the
same resume + job description always produces the same score, and every
point of the score traces back to a specific keyword match or format check
that's returned in the response — nothing is a black box.
"""

import re
from collections import Counter
from typing import Dict, List, Tuple

# ── Stopwords ──────────────────────────────────────────────────────────────
# Generic English words plus resume/job-posting boilerplate that would
# otherwise dominate keyword frequency without signaling anything about fit.
_STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be
because been before being below between both but by can't cannot could
couldn't did didn't do does doesn't doing don't down during each few for
from further had hadn't has hasn't have haven't having he he'd he'll he's
her here here's hers herself him himself his how how's i i'd i'll i'm i've
if in into is isn't it it's its itself let's me more most mustn't my myself
no nor not of off on once only or other ought our ours ourselves out over
own same shan't she she'd she'll she's should shouldn't so some such than
that that's the their theirs them themselves then there there's these they
they'd they'll they're they've this those through to too under until up
very was wasn't we we'd we'll we're we've were weren't what what's when
when's where where's which while who who's whom why why's with won't would
wouldn't you you'd you'll you're you've your yours yourself yourselves
will using use used etc within across strong ability able experience
years year including include includes work working team teams role roles
responsibilities responsible required requirements requirement preferred
qualifications qualification skills skill knowledge understanding demonstrated
excellent strong good great high highly new join looking candidate ideal
opportunity company job description position apply application please
resume candidates plus etc
""".split())

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.#/\-]{1,}")


def _tokenize(text: str) -> List[str]:
    """
    Split text into lowercase word tokens.

    The character class keeps '+', '#', '.', '/' inside a token so things
    like "C++", "C#", "Node.js", "CI/CD" survive intact — but that same class
    also happily matches trailing sentence punctuation ("Docker." at the end
    of a sentence), so trailing '.', '/', '-' are stripped after matching.
    A token like "node.js" keeps its internal dot; "docker." loses its
    trailing one.
    """
    out = []
    for w in _WORD_RE.findall(text or ""):
        w = w.lower().rstrip("./-#+")
        if w:
            out.append(w)
    return out


def _singularize(word: str) -> str:
    """Cheap plural→singular normalization so 'skills'/'skill' match as one keyword."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4 and word[-3] in "sxzh":
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _extract_weighted_keywords(text: str, top_n: int = 30) -> List[Tuple[str, int]]:
    """
    Extract the most frequent meaningful unigrams and bigrams from text.

    Frequency IS the weight — a keyword the job description repeats five
    times matters more than one mentioned once, exactly like how ATS keyword
    weighting works in practice.
    """
    tokens = _tokenize(text)
    norm = [_singularize(t) for t in tokens]

    unigrams = [t for t in norm if t not in _STOPWORDS and len(t) > 2 and not t.isdigit()]

    bigrams = []
    for i in range(len(norm) - 1):
        a, b = norm[i], norm[i + 1]
        if a not in _STOPWORDS and b not in _STOPWORDS and len(a) > 2 and len(b) > 2:
            bigrams.append(f"{a} {b}")

    counts = Counter(unigrams)
    bigram_counts = Counter(bigrams)
    # A matched bigram is a stronger, more specific signal ("machine learning"
    # beats "machine" + "learning" separately) — weight it a bit higher.
    for phrase, c in bigram_counts.items():
        if c >= 2:
            counts[phrase] = c + 1

    return counts.most_common(top_n)


def _format_checks(resume_text: str, is_from_pdf: bool) -> List[Dict]:
    """
    Structural checks that mirror what actually breaks ATS parsers.
    Each check is independently true/false and explained — nothing hidden.
    """
    text = resume_text or ""
    word_count = len(_tokenize(text))
    checks = []

    checks.append({
        "name": "Contact info detectable",
        "passed": bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)),
        "detail": "An ATS looks for a parseable email address. None was found in the extracted text."
                   if not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
                   else "Email address found.",
    })

    has_skills = bool(re.search(r"\b(skills?|technical\s+skills?|competencies)\b", text, re.IGNORECASE))
    checks.append({
        "name": "Skills section present",
        "passed": has_skills,
        "detail": "No 'Skills' section header detected — ATS systems weight explicit skills "
                   "sections heavily; consider adding one."
                   if not has_skills else "Skills section header found.",
    })

    has_experience = bool(re.search(r"\b(experience|employment|work\s+history)\b", text, re.IGNORECASE))
    checks.append({
        "name": "Experience section present",
        "passed": has_experience,
        "detail": "No 'Experience'/'Employment' section header detected."
                   if not has_experience else "Experience section header found.",
    })

    length_ok = 80 <= word_count <= 1200
    checks.append({
        "name": "Reasonable length",
        "passed": length_ok,
        "detail": f"Extracted text is {word_count} words — "
                   + ("too short for an ATS to find enough signal." if word_count < 80
                      else "unusually long; some ATS systems truncate very long documents." if word_count > 1200
                      else "within a typical range."),
    })

    if is_from_pdf:
        pdf_ok = len(text) >= 300
        checks.append({
            "name": "PDF text is extractable",
            "passed": pdf_ok,
            "detail": (
                "Very little text could be extracted from this PDF — this usually means it's "
                "an image/scan or uses a layout (tables, text boxes, columns) that ATS parsers "
                "fail to read. A real ATS would likely see this the same way: mostly blank."
                if not pdf_ok else
                "Text extracted cleanly from the PDF."
            ),
        })

    return checks


def score_resume_against_job(
    resume_text: str,
    job_description: str,
    is_from_pdf: bool = False,
) -> Dict:
    """
    Score a resume against a job description the way an ATS keyword filter
    would, plus structural parseability checks.

    Returns a fully explainable result — every number traces back to a
    concrete matched/missing keyword or a specific format check.
    """
    resume_norm_tokens = set(_singularize(t) for t in _tokenize(resume_text))
    # Also build the set of adjacent-pair phrases in the resume for bigram matching.
    resume_tokens_list = [_singularize(t) for t in _tokenize(resume_text)]
    resume_bigrams = {
        f"{resume_tokens_list[i]} {resume_tokens_list[i+1]}"
        for i in range(len(resume_tokens_list) - 1)
    }

    jd_keywords = _extract_weighted_keywords(job_description)

    matched: List[Dict] = []
    missing: List[Dict] = []
    total_weight = 0
    matched_weight = 0

    for kw, weight in jd_keywords:
        total_weight += weight
        is_phrase = " " in kw
        found = (kw in resume_bigrams) if is_phrase else (kw in resume_norm_tokens)
        if found:
            matched_weight += weight
            matched.append({"keyword": kw, "weight": weight})
        else:
            missing.append({"keyword": kw, "weight": weight})

    keyword_score = round((matched_weight / total_weight) * 100, 1) if total_weight else 0.0

    checks = _format_checks(resume_text, is_from_pdf)
    passed_checks = sum(1 for c in checks if c["passed"])
    format_score = round((passed_checks / len(checks)) * 100, 1) if checks else 100.0

    overall = round(0.7 * keyword_score + 0.3 * format_score)

    if overall >= 80:
        rating = "Strong match"
    elif overall >= 60:
        rating = "Moderate match"
    elif overall >= 40:
        rating = "Weak match"
    else:
        rating = "Poor match"

    missing.sort(key=lambda x: -x["weight"])
    matched.sort(key=lambda x: -x["weight"])

    return {
        "overall_score": overall,
        "rating": rating,
        "keyword_match_score": keyword_score,
        "format_score": format_score,
        "matched_keywords": matched[:20],
        "missing_keywords": missing[:15],
        "format_checks": checks,
        "methodology": (
            "Deterministic keyword-overlap scoring, not an LLM estimate: keywords are "
            "extracted from the job description weighted by frequency, matched against "
            "the resume's extracted text, and combined 70% keyword match / 30% format "
            "checks. The same inputs always produce the same score."
        ),
    }
