// One-click sample resumes.
//
// Pasting a resume is the single gate in front of every feature in this app --
// interview, resume analysis, ATS score and predicted questions all refuse to
// do anything until you've filled that box. That's a lot of typing to ask for
// before someone knows whether the product is any good. These let a visitor
// see a real, resume-grounded interview in one click.
//
// Written to be realistic rather than ideal: each has a genuine weakness the
// scorers will pick up (missing metrics, vague ownership, no impact figures),
// so the feedback a visitor sees is substantive instead of a lap of honour.

export type SampleResume = {
  id: string;
  label: string;
  role: string;
  text: string;
};

export const SAMPLE_RESUMES: SampleResume[] = [
  {
    id: "backend",
    label: "Backend engineer",
    role: "Backend Engineer",
    text: `Skills: Python, FastAPI, PostgreSQL, Redis, Docker, AWS

Projects:
Real-time inventory tracking service — FastAPI + websockets pushing stock
changes to warehouse clients. Postgres primary with a Redis cache in front.
Deployed on ECS behind an ALB.

Internal reporting API — nightly aggregation jobs feeding a dashboard used by
the ops team.

Experience:
2 years backend engineering at a logistics startup. Owned the inventory
service end to end, took part in on-call rotation, mentored one intern.`,
  },
  {
    id: "frontend",
    label: "Frontend engineer",
    role: "Frontend Engineer",
    text: `Skills: TypeScript, React, Next.js, Tailwind CSS, Playwright, Figma

Projects:
Customer billing portal — Next.js app for viewing invoices and updating payment
methods. Built the design system components used across three internal apps.

Accessibility pass — audited the main product surface and fixed keyboard traps
and missing labels flagged by an external review.

Experience:
3 years frontend at a B2B SaaS company. Led the migration from a legacy SPA to
the App Router, worked closely with design on the component library.`,
  },
  {
    id: "newgrad",
    label: "New graduate",
    role: "General Software Engineer",
    text: `Skills: Java, Python, SQL, Git, basic Docker

Projects:
Campus event finder — Android app that pulls university event feeds and lets
students filter by department. Final year project, worked in a team of four.

Movie recommender — collaborative filtering on the MovieLens dataset for a
machine learning coursework module.

Experience:
Six-month software engineering internship at a fintech company: wrote unit
tests for an existing payments module, fixed logged bugs, shadowed code review.
BSc Computer Science, graduated this year.`,
  },
];
