/**
 * The path's one job is to say how far a session went without misreading
 * a conditional round as a missing score.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RoundPath from "./RoundPath";

describe("a session that never reached the stress round", () => {
  it("says the round was not triggered rather than showing a blank score", () => {
    render(<RoundPath hr={7.2} technical={6.8} stress={null} />);
    expect(screen.getByText("not triggered")).toBeInTheDocument();
  });

  it("explains the trigger rule without claiming the scores held up", () => {
    // A two-question session never reaches stress regardless of how it
    // went, so asserting "your scores held" would be false for some of
    // the people reading it. The rule is true for all of them.
    render(<RoundPath hr={7.2} technical={6.8} stress={null} />);
    expect(screen.getByText(/only starts if your recent scores slip/i)).toBeInTheDocument();
    expect(screen.queryByText(/held up/i)).not.toBeInTheDocument();
  });

  it("describes the whole path as a sentence for screen readers", () => {
    render(<RoundPath hr={7.2} technical={6.8} stress={null} />);
    expect(
      screen.getByRole("img", {
        name: "Interview path: HR round 7.2, Technical round 6.8, stress round not triggered.",
      }),
    ).toBeInTheDocument();
  });
});

describe("a session that went all the way", () => {
  it("shows every round's score", () => {
    render(<RoundPath hr={6.0} technical={4.1} stress={3.5} />);
    expect(screen.getByText("6.0")).toBeInTheDocument();
    expect(screen.getByText("4.1")).toBeInTheDocument();
    expect(screen.getByText("3.5")).toBeInTheDocument();
  });

  it("does not show the trigger explanation, since it did trigger", () => {
    render(<RoundPath hr={6.0} technical={4.1} stress={3.5} />);
    expect(screen.queryByText(/only starts if/i)).not.toBeInTheDocument();
  });
});

describe("a session that ended early", () => {
  it("marks unreached non-stress rounds with a dash, not 'not triggered'", () => {
    // "Not triggered" is specific to the conditional round. A technical
    // round that never happened simply was not reached.
    render(<RoundPath hr={7.0} technical={null} stress={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getAllByText("not triggered")).toHaveLength(1);
  });

  it("offers no trigger explanation when nothing was scored at all", () => {
    render(<RoundPath hr={null} technical={null} stress={null} />);
    expect(screen.queryByText(/only starts if/i)).not.toBeInTheDocument();
  });
});

describe("compact mode, used in the history list", () => {
  it("drops the round captions and the explanation", () => {
    render(<RoundPath compact hr={7.2} technical={6.8} stress={null} />);
    expect(screen.queryByText("Technical")).not.toBeInTheDocument();
    expect(screen.queryByText(/only starts if/i)).not.toBeInTheDocument();
  });

  it("keeps the scores and the spoken description", () => {
    render(<RoundPath compact hr={7.2} technical={6.8} stress={null} />);
    expect(screen.getByText("7.2")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /stress round not triggered/i })).toBeInTheDocument();
  });
});
