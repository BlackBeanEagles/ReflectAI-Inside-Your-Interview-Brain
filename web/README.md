# ReflectInterview — Web Frontend

A Next.js (App Router, TypeScript, Tailwind CSS) frontend for ReflectInterview,
built as a full replacement for the Streamlit app in [`../frontend`](../frontend).
It talks to the exact same FastAPI backend — **no backend changes were needed**
to build this; every endpoint it calls already existed and is used as-is.

The Streamlit app stays live and untouched. This is a parallel frontend, not
a migration in place — cut over (or keep both) is your call once this has
had real usage.

## Feature parity

| Streamlit tab | This app |
|---|---|
| 🎯 Interview Session | `/` — resume input, role/language presets, live adaptive Q&A loop, voice recording + transcription, final report + PDF download |
| 📄 Resume Analysis | `/resume` |
| ✅ ATS Score | `/ats` |
| 🔮 Predicted Questions | `/predict` |
| 📊 History | `/history` |
| Sidebar login/signup/forgot password | `/login`, `/signup`, `/forgot-password`, `/reset-password` |

One difference worth knowing: auth state is stored in `localStorage` here
(see `src/lib/auth-context.tsx`), so — unlike Streamlit's `st.session_state`
— a page refresh does **not** log you out.

## Local development

```bash
npm install
cp .env.example .env.local   # then edit if you're pointing at a non-production backend
npm run dev
```

Requires **`NEXT_PUBLIC_API_BASE`** to be set (see `.env.example`) — it
defaults to the live production backend, so `npm run dev` works out of the
box without running the backend locally.

The backend's CORS allowlist (`ALLOWED_ORIGINS` / `ALLOWED_ORIGIN_REGEX` env
vars on Render) must include whatever origin you're loading this app from —
`http://localhost:3000` (or whatever port `next dev` picks) for local dev,
and the deployed Vercel domain(s) for production. See `../DEPLOY.md`.

## Deployment (Vercel)

1. [vercel.com/new](https://vercel.com/new) → import the GitHub repo.
2. Set **Root Directory** to `web` (the Next.js app lives in a subdirectory,
   not the repo root — this is the one non-default setting Vercel needs).
3. Add the environment variable `NEXT_PUBLIC_API_BASE` (same value as
   `.env.local`).
4. Deploy. Vercel auto-builds and redeploys on every push to `main`, same
   as Streamlit Cloud does for the other frontend.
5. Add the resulting `*.vercel.app` domain (and, for preview deploys, a
   regex like `^https://.*\.vercel\.app$`) to `ALLOWED_ORIGINS` /
   `ALLOWED_ORIGIN_REGEX` on the Render backend.

## Structure

```
src/
  app/                  One folder per route (App Router)
  components/
    Nav.tsx             Top nav bar (auth state, route links, health dot)
    ReportView.tsx       Renders a final report -- shared by the interview
                          flow's report phase AND the history page's
                          per-session expanders, same as Streamlit's
                          _render_report() was shared across both.
    ui.tsx               Small shared presentational primitives (buttons,
                          cards, form fields, alerts) -- not a component
                          library, just the handful of things every page uses.
  lib/
    api.ts               Typed fetch wrapper, one function per backend
                          endpoint. No backend logic duplicated here.
    types.ts              TypeScript types mirroring models/schemas.py
                          field-for-field.
    auth-context.tsx      React Context + localStorage-backed JWT session.
    hooks.ts               friendlyError(), useHealth(), usePageTitle().
```

## Design system

Colors/spacing intentionally mirror the existing Streamlit app's CSS
variables (`--ri-accent`, `--ri-tech`, `--ri-stress`, etc. — see
`src/app/globals.css`) so this reads as the same product, not a different
one. Both light and dark mode are supported via `prefers-color-scheme`,
same as the Streamlit app.
