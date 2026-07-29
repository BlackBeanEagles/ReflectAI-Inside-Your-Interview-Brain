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

Two things real ATS/resume-screening tools do that a naive keyword-count
misses, both implemented here:

    - Required vs. preferred weighting: a job posting's "must have Docker"
      matters far more than its "nice to have Docker" — keywords found in a
      sentence with required/must-have language are weighted ~1.6x; ones in
      a preferred/bonus/nice-to-have sentence are weighted ~0.6x.
    - Common synonym/abbreviation folding: "JS" and "JavaScript", "Postgres"
      and "PostgreSQL", "K8s" and "Kubernetes" are the same skill and are
      matched as such via a curated alias table. This table is necessarily
      incomplete — it is not a licensed skills taxonomy — but it removes the
      most common false "missing" flags that come purely from wording.
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
resume candidates plus etc hiring hire hires hired seeking seek employer
employers benefits salary equal employment diversity inclusive environment
culture mission vision growing fast paced dynamic passionate motivated
self starter detail oriented environment nice bonus essential minimum
""".split())

# ── Synonym / abbreviation folding ─────────────────────────────────────────
# Curated common tech aliases, not a licensed skills taxonomy — this removes
# the most frequent false "missing keyword" flags caused purely by wording
# (JD says "JavaScript", resume says "JS"), not an exhaustive equivalence.
_SYNONYMS: Dict[str, str] = {
    "js": "javascript", "javascript": "javascript",
    "ts": "typescript", "typescript": "typescript",
    "postgres": "postgresql", "postgresql": "postgresql", "psql": "postgresql",
    "k8s": "kubernetes", "kubernetes": "kubernetes",
    "reactjs": "react", "react.js": "react", "react": "react",
    "vuejs": "vue", "vue.js": "vue", "vue": "vue",
    "nodejs": "node", "node.js": "node",
    "golang": "go",
    "mongo": "mongodb", "mongodb": "mongodb",
    "py": "python", "python3": "python",
    "csharp": "c#",
    "ci/cd": "cicd", "ci-cd": "cicd",
    "nextjs": "next.js",
}

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.#/\-]{1,}")

_REQUIRED_CUES = re.compile(
    r"\b(required|require|requires|requirement|requirements|must[\s-]?have|"
    r"minimum\s+qualifications?|essential|must\s+have|need\s+to\s+have)\b",
    re.IGNORECASE,
)
_PREFERRED_CUES = re.compile(
    r"\b(preferred|preference|nice[\s-]?to[\s-]?have|bonus|is\s+a\s+plus|"
    r"a\s+plus|desirable|good\s+to\s+have|ideally)\b",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?;\n])\s+", text or "") if s.strip()]


def _sentence_weight_multiplier(sentence: str) -> float:
    """Required-language sentences count more; preferred/bonus ones count less."""
    if _REQUIRED_CUES.search(sentence):
        return 1.6
    if _PREFERRED_CUES.search(sentence):
        return 0.6
    return 1.0


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
    """
    Cheap plural→singular normalization so 'skills'/'skill' match as one
    keyword. Not real lemmatization — a hand-tuned set of suffix rules with
    guards for the false-plural cases that actually show up in resumes/job
    postings: words ending in 'us' or 'ss' ("plus", "bonus", "focus",
    "status", "analysis") are never touched, since naively stripping their
    trailing 's' produces garbage ("plus" -> "plu").
    """
    if word.endswith(("us", "ss")):
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4:
        # "boxes"/"churches"/"dishes" genuinely drop the whole "es". Words
        # like "databases"/"phrases"/"releases" only look similar because
        # their singular already ends in 'e' — for those, drop just the 's'.
        if word.endswith(("xes", "zes", "ches", "shes")):
            return word[:-2]
        return word[:-1]
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def _normalize_token(word: str) -> str:
    """Singularize, then fold through the common tech-alias table."""
    singular = _singularize(word)
    return _SYNONYMS.get(word, _SYNONYMS.get(singular, singular))


def _extract_weighted_keywords(text: str, top_n: int = 30) -> List[Tuple[str, float]]:
    """
    Extract the most important unigrams and bigrams from text.

    Weight = frequency, adjusted per-occurrence by whether the sentence it
    appeared in used required/must-have language (1.6x) or preferred/
    nice-to-have language (0.6x) — see _sentence_weight_multiplier. A
    keyword mentioned once as "required" can outweigh one mentioned twice
    as "a nice-to-have", matching how real ATS keyword weighting behaves.
    """
    counts: Counter = Counter()

    for sentence in _split_sentences(text):
        multiplier = _sentence_weight_multiplier(sentence)
        norm = [_normalize_token(t) for t in _tokenize(sentence)]

        unigrams = [t for t in norm if t not in _STOPWORDS and len(t) > 2 and not t.isdigit()]
        for t in unigrams:
            counts[t] += multiplier

        for i in range(len(norm) - 1):
            a, b = norm[i], norm[i + 1]
            if a not in _STOPWORDS and b not in _STOPWORDS and len(a) > 2 and len(b) > 2:
                phrase = f"{a} {b}"
                # A matched bigram is a stronger, more specific signal
                # ("machine learning" beats "machine" + "learning" separately).
                counts[phrase] += multiplier * 1.3

    ranked = counts.most_common(top_n)
    return [(kw, round(weight, 1)) for kw, weight in ranked]


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
    # Same normalization (singularize + synonym folding) on both sides —
    # otherwise a resume saying "JS" would never match a JD saying "JavaScript".
    resume_tokens_list = [_normalize_token(t) for t in _tokenize(resume_text)]
    resume_norm_tokens = set(resume_tokens_list)
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
            "extracted from the job description weighted by frequency, boosted ~1.6x when "
            "the posting says 'required'/'must-have' and reduced ~0.6x for "
            "'preferred'/'nice-to-have', matched against the resume (with common synonyms "
            "like JS/JavaScript and Postgres/PostgreSQL folded together), and combined "
            "70% keyword match / 30% format checks. The same inputs always produce the "
            "same score."
        ),
    }
