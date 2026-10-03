/**
 * The report is the payoff screen, and history renders the same component
 * for every past session -- so this covers both, including the history
 * page this change could not be viewed on without a live account.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ReportResponse } from "@/lib/types";
import ReportView from "./ReportView";

function report(overrides: Partial<ReportResponse> = {}): ReportResponse {
  return {
    overall_score: 6.8,
    hr_score: 7.2,
    technical_score: 6.4,
    stress_score: null,
    total_questions: 4,
    summary: "Clear on the incident timeline; thinner on trade-offs.",
    strengths: ["Structured the answer around a timeline."],
    weaknesses: ["Did not quantify the impact."],
    strength_patterns: [],
    weakness_patterns: [],
    recommendations: ["Name one number that shows the outcome."],
    behavior_tags: [],
    consistency: "",
    pressure_performance: "",
    behavior_summary: "",
    patterns: [],
    cognitive: null,
    comparison: null,
    voice_insights: null,
    ...overrides,
  } as ReportResponse;
}

describe("the interview path", () => {
  it("replaces the four equal panels with the route the session took", () => {
    render(<ReportView report={report()} />);
    expect(screen.getByRole("img", { name: /interview path/i })).toBeInTheDocument();
    expect(screen.getByText("not triggered")).toBeInTheDocument();
  });
});

describe("the interviewer's note", () => {
  it("presents the summary as a written note", () => {
    render(<ReportView report={report()} />);
    expect(screen.getByText(/interviewer's note/i)).toBeInTheDocument();
    expect(screen.getByText(/thinner on trade-offs/)).toBeInTheDocument();
  });
});

describe("debrief notes", () => {
  it("groups findings under plain-language headings", () => {
    render(<ReportView report={report()} />);
    expect(screen.getByRole("heading", { name: "What landed" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What didn't" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Next time" })).toBeInTheDocument();
  });

  it("keeps each finding as a list item a screen reader can count", () => {
    render(<ReportView report={report()} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  it("omits a heading entirely when there is nothing under it", () => {
    render(<ReportView report={report({ weaknesses: [] })} />);
    expect(screen.queryByRole("heading", { name: "What didn't" })).not.toBeInTheDocument();
  });

  it("merges overlapping strengths and patterns into one line each", () => {
    // The backend returns both lists and they overlap heavily; the report
    // used to state one observation in several boxes.
    render(
      <ReportView
        report={report({
          strengths: ["Structured the answer around a timeline."],
          strength_patterns: ["structured the answer around a timeline"],
        })}
      />,
    );
    expect(screen.getAllByText(/structured the answer around a timeline/i)).toHaveLength(1);
  });
});

describe("comparison to past sessions", () => {
  it("renders the delta with no stray leading space", () => {
    // What was left of a removed up/down glyph used to put a space in
    // front of every number here.
    render(
      <ReportView
        report={report({
          comparison: {
            overall_score: { current: 7.0, past_average: 5.8, session_count: 3, delta: 1.2 },
          },
        })}
      />,
    );
    // getByText trims before matching, so it would find " +1.2" too and
    // pass against the very bug this is about. The raw textContent is
    // what actually carried the stray space.
    expect(screen.getByText("+1.2").textContent).toBe("+1.2");
  });
});

describe("the transcript in the report", () => {
  const t = {
    question: "Why Redis?",
    answer: "For the stock cache.",
    round: "technical",
    final_score: 6,
    scores: {},
    feedback: { improvement: "Quantify it." },
  };

  it("shows the answers when the report carries them", () => {
    render(<ReportView report={report({ transcript: [t] })} />);
    expect(screen.getByText("Answer by answer")).toBeInTheDocument();
    expect(screen.getByText("Why Redis?")).toBeInTheDocument();
  });

  it("explains the absence on a report saved before answers were kept", () => {
    render(<ReportView report={report({ transcript: undefined, total_questions: 4 })} />);
    expect(screen.getByText(/isn't available for this report/i)).toBeInTheDocument();
  });

  it("says nothing for a session with no answers at all", () => {
    render(<ReportView report={report({ transcript: [], total_questions: 0 })} />);
    expect(screen.queryByText("Answer by answer")).not.toBeInTheDocument();
    expect(screen.queryByText(/isn't available/i)).not.toBeInTheDocument();
  });
});
