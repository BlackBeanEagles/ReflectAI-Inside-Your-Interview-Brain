import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { TranscriptItem } from "@/lib/types";
import Transcript from "./Transcript";

const item = (question: string, final_score: number, round = "technical"): TranscriptItem => ({
  question,
  answer: `My answer to: ${question}`,
  round,
  final_score,
  scores: {},
  feedback: { strength: "Clear.", weakness: "No numbers.", improvement: "Quantify it." },
});

describe("Transcript", () => {
  it("lists every question with its score, collapsed", () => {
    render(<Transcript items={[item("Why Redis?", 7), item("How did you scale?", 4.5)]} />);
    expect(screen.getByText("Why Redis?")).toBeInTheDocument();
    expect(screen.getByText("7.0")).toBeInTheDocument();
    expect(screen.getByText("4.5")).toBeInTheDocument();
    // Collapsed: the answer is in the DOM but not shown until opened.
    expect(screen.getByText("My answer to: Why Redis?")).not.toBeVisible();
  });

  it("shows the answer and its feedback when a question is opened", async () => {
    render(<Transcript items={[item("Why Redis?", 7)]} />);
    await userEvent.click(screen.getByText("Why Redis?"));
    expect(screen.getByText("My answer to: Why Redis?")).toBeVisible();
    expect(screen.getByText("Quantify it.")).toBeVisible();
  });

  it("points at the lowest-scoring answer, in words", () => {
    const { container } = render(
      <Transcript items={[item("A?", 7), item("B?", 3.5), item("C?", 6)]} />,
    );
    // The question rows only -- each also contains its own feedback <li>s,
    // so getAllByRole("listitem") would interleave the two.
    const rows = [...container.querySelectorAll<HTMLElement>("ol > li")];
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText("lowest score")).toBeInTheDocument();
    expect(screen.getAllByText("lowest score")).toHaveLength(1);
  });

  it("does not single anything out when there is only one answer", () => {
    render(<Transcript items={[item("A?", 3)]} />);
    expect(screen.queryByText("lowest score")).not.toBeInTheDocument();
  });

  it("names each feedback line for screen readers, not only with a symbol", async () => {
    render(<Transcript items={[item("Why Redis?", 7)]} />);
    await userEvent.click(screen.getByText("Why Redis?"));
    expect(screen.getByText("weakness:", { exact: false })).toBeInTheDocument();
  });

  it("labels the round in words", () => {
    render(<Transcript items={[item("Tell me about a conflict.", 6, "hr")]} />);
    expect(screen.getByText("HR round")).toBeInTheDocument();
  });
});
