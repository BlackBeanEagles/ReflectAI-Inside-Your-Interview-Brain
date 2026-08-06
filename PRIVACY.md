# Data handling — ReflectInterview

This app can run in two modes, controlled by the `DATABASE_URL` environment
variable on the backend.

## Without `DATABASE_URL` set (default)

Nothing is stored permanently. Resumes, answers, and scores live only in the
backend's memory for the duration of a session (auto-expired after
`SESSION_TTL_MINUTES`, default 3 hours) and are wiped entirely on every
backend restart. User accounts don't exist at all in this mode — `/auth/*`
endpoints return a clear 503 rather than pretending to work.

Resume/answer content is sent to the configured LLM provider (Ollama
locally, or Groq's API in production) to generate questions and evaluations.
Voice answers, if recorded, are sent to Groq's Whisper API for transcription
and are never written to disk — the audio bytes are forwarded in-memory and
discarded after the transcript comes back. See your provider's own data
policy for how they handle that.

## With `DATABASE_URL` set

The following is saved permanently to the connected Postgres database:

- **Resumes** — pasted text (for uploaded PDFs, only the extracted
  skills/projects/experience are saved, not the raw file) and the parsed
  skills/projects/experience. Tied to a session ID (a random UUID) and,
  if the person is logged in, their user ID.
- **Interactions** — every question, the candidate's answer, per-dimension
  scores, final score, and AI feedback.
- **Reports** — the generated final report for each session.
- **User accounts** (only if someone signs up) — email address, a bcrypt
  hash of their password (never the plaintext password itself, which is
  discarded immediately after hashing), and optionally a display name.

Persistence of resumes/interactions/reports still requires the explicit
consent checkbox shown on the setup screen — having `DATABASE_URL` set does
not by itself mean everyone's data gets saved. Creating an account is a
separate, independent action from that consent checkbox; an account by
itself doesn't cause anything to persist unless consent is also given during
a session.

None of this is currently deleted automatically, anonymized, or exposed to
the person it belongs to for self-service review/export. Before pointing
real users at a deployment with persistence and/or accounts enabled, you are
responsible for:

- Telling users clearly, before they submit anything, that their resume and
  answers will be stored.
- Providing a way for someone to request their data (including their
  account) be deleted, if you're subject to GDPR/CCPA or similar.
- Deciding a retention policy (this app does not currently delete old rows).
- Setting `JWT_SECRET_KEY` explicitly (see `.env.example`) — without it, a
  random secret is generated per process start, which silently logs out
  every user on every restart/redeploy. Not a data-exposure risk, but a
  real reliability one worth knowing about.

This file is a technical summary, not a privacy policy — it doesn't
constitute legal advice or a substitute for one if you have real users.
