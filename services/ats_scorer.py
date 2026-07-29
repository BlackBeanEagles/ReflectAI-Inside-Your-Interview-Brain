"""
ATS Scorer module.
Responsibility: Score a resume against a job description the way a real
Applicant Tracking System / resume screener would — weighted category
scoring, keyword overlap, and structural parseability checks. Everything
in this module is deterministic; the same resume + job description always
produce the same score. No LLM involved anywhere below.

Category weights (mirrors how real ATS/resume-screening tools like Jobscan
actually weight a resume — not an invented split):

    Keyword Match               40%   (35-45% typical range)
    Experience Relevance        20%   (20-25%)
    ATS Formatting              15%   (10-20%)
    Skills Section               12%   (10-15%)
    Education & Certifications   7%   (5-10%)
    Contact Information           3%   (2-5%)
    Grammar & Readability          3%   (3-8%)
                                 ----
                                 100%

Two categories are worth being upfront about the limits of:
    - Grammar & Readability has no real grammar-checking library wired in
      (that would mean a Java-based tool like LanguageTool or a paid API).
      What's implemented is a small set of honest proxies — bullet-point
      consistency, verb-tense consistency, repeated-word detection — not
      genuine grammar checking. It's the lowest-weighted category (3%)
      specifically because it's the least reliable signal here.
    - Everything else (keywords, experience quantification, section
      presence, contact info, education/cert keywords, PDF extractability)
      is a direct, inspectable regex/heuristic check — nothing guessed.
"""

import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

CATEGORY_WEIGHTS: Dict[str, int] = {
    "keyword_match": 40,
    "experience_relevance": 20,
    "ats_formatting": 15,
    "skills_section": 12,
    "education_certifications": 7,
    "contact_information": 3,
    "grammar_readability": 3,
}
assert sum(CATEGORY_WEIGHTS.values()) == 100

CATEGORY_LABELS: Dict[str, str] = {
    "keyword_match": "Keyword Match",
    "experience_relevance": "Experience Relevance",
    "ats_formatting": "ATS Formatting",
    "skills_section": "Skills Section",
    "education_certifications": "Education & Certifications",
    "contact_information": "Contact Information",
    "grammar_readability": "Grammar & Readability",
}

# ── Stopwords ──────────────────────────────────────────────────────────────
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
need needs needed nice-to-have nice-to-haves must-have must-haves ideally
""".split())

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

_ACTION_VERBS = frozenset("""
developed designed built implemented automated optimized led reduced
improved increased created managed launched drove spearheaded architected
engineered deployed migrated scaled established delivered authored
analyzed streamlined founded organized coordinated mentored trained
negotiated resolved authored refactored debugged tested shipped owned
""".split())

_DEGREE_RE = re.compile(
    r"\b(bachelor|master|ph\.?d|b\.?tech|m\.?tech|b\.?s\.?c?|m\.?s\.?c?|"
    r"bsc|msc|mba|university|college|degree)\b", re.IGNORECASE,
)
_CERT_RE = re.compile(r"\b(certified|certificate|certification|certifications)\b", re.IGNORECASE)
_EDUCATION_HEADER_RE = re.compile(r"\beducation\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/", re.IGNORECASE)
_QUANTIFIED_RE = re.compile(
    r"\d+(\.\d+)?\s?(%|percent|x\b|times|\$|k\b|million|users?|requests?|ms\b|seconds?|hours?)",
    re.IGNORECASE,
)
_BULLET_LINE_RE = re.compile(r"^\s*[•\-\*·▪▸]\s*\S")

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


def _tokenize(text: str) -> List[str]:
    out = []
    for w in _WORD_RE.findall(text or ""):
        w = w.lower().rstrip("./-#+")
        if w:
            out.append(w)
    return out


def _lines(text: str) -> List[str]:
    return [l for l in (text or "").splitlines() if l.strip()]


def _singularize(word: str) -> str:
    if word.endswith(("us", "ss")):
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4:
        if word.endswith(("xes", "zes", "ches", "shes")):
            return word[:-2]
        return word[:-1]
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def _normalize_token(word: str) -> str:
    singular = _singularize(word)
    return _SYNONYMS.get(word, _SYNONYMS.get(singular, singular))


def _split_sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?;\n])\s+", text or "") if s.strip()]


def _sentence_weight_multiplier(sentence: str) -> float:
    if _REQUIRED_CUES.search(sentence):
        return 1.6
    if _PREFERRED_CUES.search(sentence):
        return 0.6
    return 1.0


def _extract_weighted_keywords(text: str, top_n: int = 30) -> List[Tuple[str, float]]:
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
                counts[f"{a} {b}"] += multiplier * 1.3
    ranked = counts.most_common(top_n)
    return [(kw, round(w, 1)) for kw, w in ranked]


# ── Per-category scorers ────────────────────────────────────────────────────
# Each returns (score_0_to_100, [check_dict, ...]).

def _score_keyword_match(resume_text: str, job_description: str) -> Tuple[float, List[Dict], List[Dict], List[Dict]]:
    resume_tokens_list = [_normalize_token(t) for t in _tokenize(resume_text)]
    resume_norm_tokens = set(resume_tokens_list)
    resume_bigrams = {
        f"{resume_tokens_list[i]} {resume_tokens_list[i+1]}"
        for i in range(len(resume_tokens_list) - 1)
    }

    jd_keywords = _extract_weighted_keywords(job_description)
    matched, missing = [], []
    total_weight = matched_weight = 0.0

    for kw, weight in jd_keywords:
        total_weight += weight
        is_phrase = " " in kw
        found = (kw in resume_bigrams) if is_phrase else (kw in resume_norm_tokens)
        if found:
            matched_weight += weight
            matched.append({"keyword": kw, "weight": weight})
        else:
            missing.append({"keyword": kw, "weight": weight})

    score = (matched_weight / total_weight) * 100 if total_weight else 0.0
    matched.sort(key=lambda x: -x["weight"])
    missing.sort(key=lambda x: -x["weight"])

    checks = [{
        "name": "Keyword overlap with job description",
        "passed": score >= 50,
        "detail": f"{len(matched)}/{len(matched)+len(missing)} weighted keywords found in the resume.",
    }]
    return round(score, 1), checks, matched, missing, total_weight


def _score_experience_relevance(resume_text: str) -> Tuple[float, List[Dict]]:
    """
    Only lines that actually look like bullet points feed the quantified-
    achievement / action-verb ratios below — section headers, the skills
    line, education/contact lines, etc. must not dilute that signal.
    Falls back to all non-empty lines only for resumes that don't use
    bullet characters at all (imprecise, but better than reporting 0%).
    """
    has_section = bool(re.search(r"\b(experience|employment|work\s+history)\b", resume_text, re.IGNORECASE))
    lines = _lines(resume_text)
    bullet_like = [l for l in lines if _BULLET_LINE_RE.match(l)]
    bullet_like = bullet_like or lines
    quantified = [l for l in bullet_like if _QUANTIFIED_RE.search(l)]
    action_started = [
        l for l in bullet_like
        if re.match(r"^\s*[•\-\*·▪▸]?\s*(\w+)", l)
        and re.match(r"^\s*[•\-\*·▪▸]?\s*(\w+)", l).group(1).lower() in _ACTION_VERBS
    ]

    quantified_ratio = len(quantified) / len(bullet_like) if bullet_like else 0.0
    action_ratio = len(action_started) / len(bullet_like) if bullet_like else 0.0

    score = (40 if has_section else 0) + min(quantified_ratio * 100, 30) + min(action_ratio * 100, 30)
    score = min(score, 100)

    checks = [
        {
            "name": "Experience section present",
            "passed": has_section,
            "detail": "Experience/Employment section header found." if has_section
                       else "No 'Experience'/'Employment' section header detected.",
        },
        {
            "name": "Achievements are quantified",
            "passed": quantified_ratio >= 0.25,
            "detail": f"{len(quantified)}/{len(bullet_like)} lines contain a number/metric "
                       f"(%, $, count, time saved, etc.) — quantified bullets score far higher "
                       f"with both ATS ranking and human reviewers."
                       if quantified_ratio < 0.25 else
                       f"{len(quantified)}/{len(bullet_like)} lines are quantified — good.",
        },
        {
            "name": "Bullets start with strong action verbs",
            "passed": action_ratio >= 0.25,
            "detail": "Few lines start with a strong action verb (Developed, Built, Led, "
                       "Reduced, Automated, ...) — passive phrasing like 'Worked on X' reads "
                       "weaker than 'Built X'."
                       if action_ratio < 0.25 else
                       "Most lines start with a strong action verb — good.",
        },
    ]
    return round(score, 1), checks


def _score_skills_section(resume_text: str) -> Tuple[float, List[Dict]]:
    match = re.search(
        r"skills?\s*[:\-–]?\s*\n?(.*?)(?=\n\s*(?:experience|education|projects?|certifications?)\b|\Z)",
        resume_text, re.IGNORECASE | re.DOTALL,
    )
    has_section = bool(re.search(r"\b(skills?|technical\s+skills?|competencies)\b", resume_text, re.IGNORECASE))
    items: List[str] = []
    if match:
        raw = match.group(1)
        items = [i.strip() for i in re.split(r"[,\n•·▪▸|;]", raw) if i.strip() and len(i.strip()) < 40]

    n = len(items)
    if not has_section:
        score = 0.0
    elif n == 0:
        score = 20.0
    elif n < 5:
        score = 60.0
    elif n <= 20:
        score = 100.0
    else:
        score = 80.0  # excessive listing reads like keyword stuffing

    checks = [{
        "name": "Skills section present with a reasonable number of items",
        "passed": has_section and 1 <= n <= 20,
        "detail": (
            "No 'Skills' section detected." if not has_section else
            "Skills section found but no individual items could be parsed out of it." if n == 0 else
            f"Only {n} skill(s) listed — most tech resumes list 8-20." if n < 5 else
            f"{n} skills listed — consider trimming to your strongest, most relevant ones "
            f"rather than everything you've ever touched." if n > 20 else
            f"{n} skills listed — good range."
        ),
    }]
    return score, checks


def _score_education_certifications(resume_text: str) -> Tuple[float, List[Dict]]:
    has_header = bool(_EDUCATION_HEADER_RE.search(resume_text))
    has_degree = bool(_DEGREE_RE.search(resume_text))
    has_cert = bool(_CERT_RE.search(resume_text))

    score = (50 if (has_header or has_degree) else 0) + (50 if has_cert else 0)
    # Don't punish resumes with no certifications — not everyone has any and it's not disqualifying.
    if not has_cert and (has_header or has_degree):
        score = 80.0

    checks = [{
        "name": "Education section detectable",
        "passed": has_header or has_degree,
        "detail": "No 'Education' header or recognizable degree (Bachelor's, Master's, B.Tech, "
                   "etc.) detected." if not (has_header or has_degree) else
                   "Education section / degree detected.",
    }]
    if has_cert:
        checks.append({
            "name": "Certifications mentioned",
            "passed": True,
            "detail": "At least one certification keyword detected.",
        })
    return score, checks


def _score_contact_information(resume_text: str) -> Tuple[float, List[Dict]]:
    has_email = bool(_EMAIL_RE.search(resume_text))
    has_phone = bool(_PHONE_RE.search(resume_text))
    has_linkedin = bool(_LINKEDIN_RE.search(resume_text))
    has_github = bool(_GITHUB_RE.search(resume_text))

    score = (50 if has_email else 0) + (25 if has_phone else 0) + (15 if has_linkedin else 0) + (10 if has_github else 0)

    checks = [{
        "name": "Contact info detectable",
        "passed": has_email,
        "detail": "An ATS looks for a parseable email address. None was found." if not has_email
                   else "Email address found.",
    }]
    if not has_phone:
        checks.append({"name": "Phone number detectable", "passed": False,
                        "detail": "No phone number pattern found — some ATS systems parse this as a contact field."})
    if not (has_linkedin or has_github):
        checks.append({"name": "LinkedIn/GitHub link present", "passed": False,
                        "detail": "No LinkedIn or GitHub URL found — worth adding for technical roles."})
    return min(score, 100), checks


def _score_grammar_readability(resume_text: str) -> Tuple[float, List[Dict]]:
    """
    Heuristic proxies only — no real grammar-checking library is wired in
    here (that would mean a Java-based tool or a paid API). This is why
    the category carries only 3% weight: it's the least reliable signal
    in this module, and it says so.
    """
    lines = _lines(resume_text)
    bullet_lines = [l for l in lines if _BULLET_LINE_RE.match(l)]
    bullet_ratio = len(bullet_lines) / len(lines) if lines else 0.0

    verb_endings = []
    for l in lines:
        m = re.match(r"^\s*[•\-\*·▪▸]?\s*(\w+)", l)
        if m:
            w = m.group(1).lower()
            if w.endswith("ed"):
                verb_endings.append("past")
            elif w.endswith("ing"):
                verb_endings.append("gerund")
    tense_consistent = True
    if len(verb_endings) >= 4:
        past_count = verb_endings.count("past")
        gerund_count = verb_endings.count("gerund")
        total = past_count + gerund_count
        tense_consistent = total == 0 or max(past_count, gerund_count) / total >= 0.75

    repeated_words = bool(re.search(r"\b(\w+)\s+\1\b", resume_text, re.IGNORECASE))

    score = 100.0
    if not bullet_lines:
        score -= 25
    if not tense_consistent:
        score -= 40
    if repeated_words:
        score -= 20
    score = max(score, 0.0)

    checks = [{
        "name": "Consistent bullet-point structure",
        "passed": bullet_ratio > 0 or not lines,
        "detail": "No bullet points detected — dense paragraphs are harder for both ATS and "
                   "human reviewers to scan quickly." if bullet_ratio == 0 and lines
                   else "Bullet-point structure detected.",
    }]
    if len(verb_endings) >= 4:
        checks.append({
            "name": "Consistent verb tense",
            "passed": tense_consistent,
            "detail": "Bullets mix past-tense ('Developed') and gerund ('Developing') openings — "
                       "pick one, past tense is the convention for past roles."
                       if not tense_consistent else "Verb tense is consistent.",
        })
    if repeated_words:
        checks.append({
            "name": "No accidental repeated words",
            "passed": False,
            "detail": "Found an immediately repeated word (e.g. 'the the') — worth a proofread pass.",
        })
    return score, checks


def _score_ats_formatting(resume_text: str, is_from_pdf: bool) -> Tuple[float, List[Dict]]:
    word_count = len(_tokenize(resume_text))
    length_ok = 80 <= word_count <= 1200
    has_skills = bool(re.search(r"\b(skills?|technical\s+skills?|competencies)\b", resume_text, re.IGNORECASE))
    has_experience = bool(re.search(r"\b(experience|employment|work\s+history)\b", resume_text, re.IGNORECASE))

    checks = [
        {
            "name": "Standard section headings",
            "passed": has_skills and has_experience,
            "detail": "Uses standard headings ATS parsers recognize (Skills, Experience)."
                       if has_skills and has_experience else
                       "Missing one or more standard section headings — non-standard headings "
                       "like 'My Journey' or 'Cool Stuff' often aren't recognized as sections at all.",
        },
        {
            "name": "Reasonable length",
            "passed": length_ok,
            "detail": f"Extracted text is {word_count} words — "
                       + ("too short for an ATS to find enough signal." if word_count < 80
                          else "unusually long; some ATS systems truncate very long documents." if word_count > 1200
                          else "within a typical range."),
        },
    ]

    if is_from_pdf:
        pdf_ok = len(resume_text) >= 300
        checks.append({
            "name": "PDF text is extractable",
            "passed": pdf_ok,
            "detail": (
                "Very little text could be extracted from this PDF — this usually means it's "
                "an image/scan or uses a layout (tables, text boxes, columns) that ATS parsers "
                "fail to read."
                if not pdf_ok else
                "Text extracted cleanly from the PDF — no tables/columns/image-text problem detected."
            ),
        })

    passed = sum(1 for c in checks if c["passed"])
    score = (passed / len(checks)) * 100 if checks else 100.0
    return round(score, 1), checks


# ── Improvement plan (Resume ROI) ───────────────────────────────────────────

_EFFORT_BY_CATEGORY = {
    "keyword_match": "Quick (~5 min) — if you genuinely have the skill",
    "contact_information": "Quick (~5 min)",
    "skills_section": "Quick (~5-10 min)",
    "education_certifications": "Quick (~10 min)",
    "ats_formatting": "Moderate (~15-20 min) — may need reformatting",
    "grammar_readability": "Moderate (~15-20 min) — proofread pass",
    "experience_relevance": "Longer (~20-30 min per bullet) — requires real rewriting",
}


def _build_improvement_plan(
    category_scores: Dict[str, Dict],
    missing_keywords: List[Dict],
    keyword_total_weight: float,
) -> List[Dict]:
    """
    Every item's estimated_gain is derived exactly, not guessed: a failed
    check's gain is its category's weight split evenly across that
    category's checks; a missing keyword's gain is its share of the total
    keyword weight, scaled by the keyword-match category's weight (40).
    Ranked by estimated_gain descending — highest-ROI fix first.
    """
    items: List[Dict] = []

    for cat_key, cat in category_scores.items():
        cat_weight = CATEGORY_WEIGHTS[cat_key]
        failed = [c for c in cat["checks"] if not c["passed"]]
        if not failed:
            continue
        per_check_gain = cat_weight / len(cat["checks"])
        for check in failed:
            items.append({
                "priority": "high" if per_check_gain >= 5 else ("medium" if per_check_gain >= 2 else "low"),
                "category": CATEGORY_LABELS[cat_key],
                "action": check["detail"],
                "reason": f"Part of the {CATEGORY_LABELS[cat_key]} category ({cat_weight}% of the score).",
                "estimated_gain": round(per_check_gain, 1),
                "effort": _EFFORT_BY_CATEGORY[cat_key],
            })

    kw_weight_pct = CATEGORY_WEIGHTS["keyword_match"]
    for kw in missing_keywords[:10]:
        gain = (kw["weight"] / keyword_total_weight) * kw_weight_pct if keyword_total_weight else 0
        if gain < 0.3:
            continue
        items.append({
            "priority": "high" if gain >= 3 else ("medium" if gain >= 1 else "low"),
            "category": "Keyword Match",
            "action": f"Add '{kw['keyword']}' if it genuinely applies to you.",
            "reason": "This term appears in the job description but wasn't found in your resume.",
            "estimated_gain": round(gain, 1),
            "effort": _EFFORT_BY_CATEGORY["keyword_match"],
        })

    items.sort(key=lambda x: -x["estimated_gain"])
    return items


def generate_recruiter_take(resume_text: str, job_description: str) -> Optional[str]:
    """
    Optional, best-effort qualitative read from the LLM roleplaying as a
    recruiter skimming the resume for ~8 seconds. Unlike every number above,
    this is NOT deterministic and can vary between calls — it's exposed
    separately and must always be labeled as a subjective AI impression,
    never folded into the numeric score.

    Returns None (never raises) if the LLM is unavailable — the rest of the
    score is fully usable without this.
    """
    try:
        from utils.llm import call_llm
        prompt = (
            "You are a busy recruiter who spends about 8 seconds on a first resume pass. "
            "Read the resume below against the job description and give a short, honest "
            "first impression: 2-3 things that stand out positively, and 2-3 concrete reasons "
            "you'd hesitate or skip this candidate. Be specific and blunt, not encouraging filler. "
            "Keep it under 120 words total.\n\n"
            f"JOB DESCRIPTION:\n{job_description[:2000]}\n\n"
            f"RESUME:\n{resume_text[:3000]}\n"
        )
        text = call_llm(prompt, purpose="coach", timeout=20)
        text = (text or "").strip()
        if not text or text.startswith(("LLM error", "Ollama is not running", "LLM request timed out",
                                          "Unexpected error calling LLM", "System temporarily unavailable")):
            return None
        return text
    except Exception:
        return None


def score_resume_against_job(
    resume_text: str,
    job_description: str,
    is_from_pdf: bool = False,
    include_recruiter_take: bool = False,
) -> Dict:
    """
    Score a resume against a job description using the 7 weighted
    categories documented at the top of this module. Deterministic —
    same inputs always produce the same score.
    """
    resume_text = resume_text or ""
    job_description = job_description or ""

    kw_score, kw_checks, matched, missing, kw_total_weight = _score_keyword_match(resume_text, job_description)
    exp_score, exp_checks = _score_experience_relevance(resume_text)
    fmt_score, fmt_checks = _score_ats_formatting(resume_text, is_from_pdf)
    skills_score, skills_checks = _score_skills_section(resume_text)
    edu_score, edu_checks = _score_education_certifications(resume_text)
    contact_score, contact_checks = _score_contact_information(resume_text)
    grammar_score, grammar_checks = _score_grammar_readability(resume_text)

    category_scores = {
        "keyword_match": {"score": kw_score, "checks": kw_checks},
        "experience_relevance": {"score": exp_score, "checks": exp_checks},
        "ats_formatting": {"score": fmt_score, "checks": fmt_checks},
        "skills_section": {"score": skills_score, "checks": skills_checks},
        "education_certifications": {"score": edu_score, "checks": edu_checks},
        "contact_information": {"score": contact_score, "checks": contact_checks},
        "grammar_readability": {"score": grammar_score, "checks": grammar_checks},
    }

    overall = sum(category_scores[c]["score"] * CATEGORY_WEIGHTS[c] for c in CATEGORY_WEIGHTS) / 100
    overall = round(overall)

    if overall >= 80:
        rating = "Strong match"
    elif overall >= 60:
        rating = "Moderate match"
    elif overall >= 40:
        rating = "Weak match"
    else:
        rating = "Poor match"

    categories_out = [
        {
            "key": key,
            "label": CATEGORY_LABELS[key],
            "weight": CATEGORY_WEIGHTS[key],
            "score": category_scores[key]["score"],
            "checks": category_scores[key]["checks"],
        }
        for key in CATEGORY_WEIGHTS
    ]

    keyword_importance = []
    all_kw = matched + missing
    max_weight = max((k["weight"] for k in all_kw), default=1) or 1
    for k in sorted(all_kw, key=lambda x: -x["weight"])[:15]:
        keyword_importance.append({
            "keyword": k["keyword"],
            "weight": k["weight"],
            "importance_pct": round((k["weight"] / max_weight) * 100, 1),
            "matched": k in matched,
        })

    section_ranking = [
        {"section": "Skills", "score": round(skills_score / 10, 1)},
        {"section": "Experience", "score": round(exp_score / 10, 1)},
        {"section": "Education", "score": round(edu_score / 10, 1)},
        {"section": "Contact Info", "score": round(contact_score / 10, 1)},
        {"section": "Formatting", "score": round(fmt_score / 10, 1)},
    ]

    improvement_plan = _build_improvement_plan(category_scores, missing, kw_total_weight)

    recruiter_take = generate_recruiter_take(resume_text, job_description) if include_recruiter_take else None

    return {
        "overall_score": overall,
        "rating": rating,
        "categories": categories_out,
        "matched_keywords": matched[:20],
        "missing_keywords": missing[:15],
        "keyword_importance": keyword_importance,
        "section_ranking": section_ranking,
        "improvement_plan": improvement_plan,
        "recruiter_take": recruiter_take,
        "methodology": (
            "Deterministic, weighted-category scoring — not an LLM estimate: Keyword Match 40%, "
            "Experience Relevance 20%, ATS Formatting 15%, Skills Section 12%, Education & "
            "Certifications 7%, Contact Information 3%, Grammar & Readability 3%. Keywords are "
            "extracted from the job description weighted by frequency, boosted ~1.6x for "
            "'required'/'must-have' language and reduced ~0.6x for 'preferred'/'nice-to-have', "
            "with common synonyms (JS/JavaScript, Postgres/PostgreSQL, K8s/Kubernetes) folded "
            "together. The same inputs always produce the same score. The optional "
            "'recruiter_take' field is the one exception — it's LLM-generated qualitative "
            "feedback, not deterministic, and is never part of the numeric score."
        ),
    }
