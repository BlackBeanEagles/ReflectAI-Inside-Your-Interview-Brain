import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { PredictedQuestionItem } from "@/lib/types";
import PrepChecklist from "./PrepChecklist";

const Q = (question: string, category: PredictedQuestionItem["category"] = "technical") => ({
  question,
  category,
  prep_tip: "Use one concrete example.",
});

afterEach(() => localStorage.clear());

describe("PrepChecklist", () => {
  it("counts practised questions as they are ticked", async () => {
    render(<PrepChecklist questions={[Q("How does Redis evict keys?"), Q("Why Postgres?")]} />);
    expect(screen.getByText("0 of 2 practised")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: /redis/i }));
    expect(screen.getByText("1 of 2 practised")).toBeInTheDocument();
  });

  it("can untick a question", async () => {
    render(<PrepChecklist questions={[Q("Why Postgres?")]} />);
    const box = screen.getByRole("checkbox", { name: /postgres/i });
    await userEvent.click(box);
    await userEvent.click(box);
    expect(screen.getByText("0 of 1 practised")).toBeInTheDocument();
  });

  it("remembers ticks across a regenerated list, by question text", async () => {
    // The generator often repeats some questions; those should come back
    // already done rather than resetting with the list.
    const { unmount } = render(<PrepChecklist questions={[Q("Why Postgres?"), Q("Old one?")]} />);
    await userEvent.click(screen.getByRole("checkbox", { name: /postgres/i }));
    unmount();

    render(<PrepChecklist questions={[Q("why postgres?"), Q("A new one?")]} />);
    expect(screen.getByRole("checkbox", { name: /postgres/i })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /new one/i })).not.toBeChecked();
    expect(screen.getByText("1 of 2 practised")).toBeInTheDocument();
  });

  it("still works when storage is unavailable", async () => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new DOMException("blocked", "SecurityError");
    };
    try {
      render(<PrepChecklist questions={[Q("Why Postgres?")]} />);
      await userEvent.click(screen.getByRole("checkbox", { name: /postgres/i }));
      expect(screen.getByText("1 of 1 practised")).toBeInTheDocument();
    } finally {
      Storage.prototype.setItem = original;
    }
  });

  it("groups questions under their category", () => {
    render(<PrepChecklist questions={[Q("Tell me about a conflict?", "behavioral"), Q("Why Go?")]} />);
    expect(screen.getByRole("heading", { name: "Behavioural" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Technical" })).toBeInTheDocument();
  });

  it("names each checkbox by its question alone, with the tip as its description", () => {
    render(<PrepChecklist questions={[Q("Why Postgres?")]} />);
    const box = screen.getByRole("checkbox", { name: "Why Postgres?" });
    expect(box).toHaveAccessibleDescription("Use one concrete example.");
  });
});
