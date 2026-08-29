# Deploying ReflectInterview for free

Two pieces, hosted separately, both on free tiers:

| Piece | Where | Why |
|---|---|---|
| Backend (FastAPI) | Render free web service (Docker) | Free tier, supports the `Dockerfile` in this repo directly |
| Frontend | **`web/` (Next.js)**, recommended — see step 3 below | The current, feature-complete frontend (see `web/README.md`'s parity table) |
| LLM | Groq API | Free tier, no card, fast — no GPU needed (unlike Ollama) |

`frontend/app.py` (Streamlit) is the older frontend this one replaced — it
still works and can still be deployed to Streamlit Community Cloud if you
prefer it, but `web/` is what's actively maintained and what these steps
deploy by default.

Local dev keeps using Ollama (`LLM_PROVIDER=ollama`, the default) — nothing
changes for that workflow. Production should use Groq instead, because no free
web host gives you the RAM/GPU an 8B Ollama model needs.

## 1. Get a free Groq API key

1. Go to https://console.groq.com and sign up (no card required).
2. Create an API key.
3. Keep it — you'll paste it into Render's dashboard in step 2, not into any file.

## 2. Deploy the backend to Render

1. Push this repo to GitHub (if it isn't already).
2. On https://render.com → **New +** → **Web Service** → connect the repo.
3. Render will detect the `Dockerfile` automatically. Leave build/start commands blank.
4. Under **Environment**, add:
   - `LLM_PROVIDER` = `groq`
   - `GROQ_API_KEY` = *(your key from step 1 — this also powers voice input's
     speech-to-text, independent of which LLM_PROVIDER you pick)*
   - `ALLOWED_ORIGINS` = `http://localhost:8501` *(update after step 3 below)*
5. Deploy. Render gives you a URL like `https://reflectinterview-api.onrender.com`.
6. Confirm it's alive: open `https://<your-render-url>/health` — you should see
   `{"api":"ok","provider":"groq",...}`.

**Free-tier note:** Render's free web services spin down after ~15 minutes of
no traffic and take a few seconds to wake back up on the next request — the
first request after idle will be slow, not broken. This is expected on free
hosting, not a bug.

## 3. Deploy the frontend (`web/`) to Vercel

1. Go to https://vercel.com → **Add New → Project** → import this repo.
2. Set **Root Directory** to `web` (Vercel auto-detects it's a Next.js app
   once you do — leave the build/output settings at their defaults).
3. Under **Environment Variables**, add:
   ```
   NEXT_PUBLIC_API_BASE = https://<your-render-url>
   ```
4. Deploy. You'll get a URL like `https://your-app.vercel.app`.

## 4. Point the backend's CORS at the real frontend URL

Go back to Render → your service → **Environment** → update:

```
ALLOWED_ORIGINS=https://your-app.vercel.app
```

(Multiple origins are comma-separated if you also want to keep localhost
working for local testing against the hosted backend, e.g.
`http://localhost:3000,https://your-app.vercel.app`.)

Redeploy the backend for the change to take effect.

## 5. Verify end to end

Open the Vercel URL. The nav bar's status dot next to the logo should be
green (backend reachable). Paste a resume and run through one question — if
`ALLOWED_ORIGINS` is wrong you'll see a CORS error in the browser console
rather than a normal response; double-check step 4.

## Alternative: the older Streamlit frontend

`frontend/app.py` still works if you'd rather use it instead of (or
alongside) `web/`:

1. Go to https://share.streamlit.io → **New app** → point it at this repo,
   main file path `frontend/app.py`.
2. Under **Advanced settings → Secrets**, add:
   ```toml
   BACKEND_BASE = "https://<your-render-url>"
   ```
3. Deploy, then add the resulting `https://your-app.streamlit.app` URL to
   `ALLOWED_ORIGINS` on the backend the same way as step 4 above.

## What's already handled for a public deployment

These aren't things you need to configure — they're built into the code so a
stranger hitting your free-hosted URL can't take it down or run up unexpected
cost:

- **Rate limiting** — 20 requests/60s per IP on the expensive endpoints
  (`RATE_LIMIT_WINDOW_S` / `RATE_LIMIT_MAX_REQUESTS` in `.env.example` if you
  want to tune it).
- **Upload/input caps** — resumes over 5MB (PDF) or 20,000 characters (pasted
  text), and answers over 6,000 characters, are rejected with a clear error
  instead of eating memory or LLM tokens unbounded.
- **Session eviction** — interview sessions are held in memory and expire
  after 3 hours of inactivity (`SESSION_TTL_MINUTES`), with a hard cap of 500
  concurrent sessions (`MAX_SESSIONS`) that evicts the oldest once hit. Without
  this, sessions from every visitor who ever loaded the page would accumulate
  forever and eventually run the process out of memory.

## Optional: permanent storage with Neon (free Postgres)

By default nothing survives a backend restart — resumes and answers live only
in memory for the session. To save them permanently instead:

1. Go to https://neon.tech, sign up (no card required), create a project.
2. Copy the connection string it gives you (starts with `postgresql://`).
3. On Render → your service → **Environment**, add:
   ```
   DATABASE_URL=<the connection string from Neon>
   ```
4. Redeploy. `/health` should now show `"storage":"postgres"` instead of
   `"storage":"in-memory-only"`. Tables are created automatically on startup.

With this set, the frontend shows a consent checkbox on the setup screen
("Save my resume and interview answers...") — nothing is persisted unless a
user explicitly checks it, even with `DATABASE_URL` configured. See
[PRIVACY.md](PRIVACY.md) for exactly what gets stored and your responsibilities
before pointing real users at a deployment with this enabled.

## Known limitation: single instance only

Session state lives in the backend process's memory (see
`services/session_manager.py`). This works correctly on Render's free tier
(one instance), but does **not** survive a redeploy/restart, and would not
work correctly if you ever scaled to multiple backend instances — sessions
would randomly disappear depending on which instance served a given request.
Fixing that needs a shared store (Redis, Postgres) and is a deliberate
non-goal while running everything for free.

## Costs if you outgrow the free tiers

- Groq's free tier has generous but real rate limits shared across your whole
  app's traffic. If you get real usage, a low-cost Groq/OpenAI paid tier
  removes that ceiling.
- Render's free web service sleeps when idle. Their cheapest paid tier (a few
  dollars/month) keeps it always-on, removing the wake-up delay.
- Neither is required to launch — just something to revisit once you have
  actual users and are ready to talk about charging them (this session
  deliberately left billing out of scope).
