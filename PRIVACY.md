# Data handling — ReflectInterview

This app can run in two modes, controlled by the `DATABASE_URL` environment
variable on the backend.

## Without `DATABASE_URL` set (default)

Nothing is stored permanently. Resumes, answers, and scores live only in the
backend's memory for the duration of a session (auto-expired after
`SESSION_TTL_MINUTES`, default 3 hours) and are wiped entirely on every
backend restart. Resume/answer content is also sent to the configured LLM
provider (Ollama locally, or Groq's API in production) to generate questions
and evaluations — see your provider's own data policy for how they handle
that.

## With `DATABASE_URL` set

The following is saved permanently to the connected Postgres database, tied
to a session ID (a random UUID, not linked to any real-world identity unless
the resume content itself names the person):

- **Resumes** — pasted text (for uploaded PDFs, only the extracted
  skills/projects/experience are saved, not the raw file) and the parsed
  skills/projects/experience.
- **Interactions** — every question, the candidate's answer, per-dimension
  scores, final score, and AI feedback.
- **Reports** — the generated final report for each session.

None of this is currently deleted automatically, anonymized, or exposed to
the person it belongs to. Before pointing real users at a deployment with
persistence enabled, you are responsible for:

- Telling users clearly, before they submit anything, that their resume and
  answers will be stored (the app shows a consent checkbox on the setup
  screen for this).
- Providing a way for someone to request their data be deleted, if you're
  subject to GDPR/CCPA or similar.
- Deciding a retention policy (this app does not currently delete old rows).

This file is a technical summary, not a privacy policy — it doesn't
constitute legal advice or a substitute for one if you have real users.
