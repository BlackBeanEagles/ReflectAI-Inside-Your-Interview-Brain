/**
 * The pacing meter's job is to be honest about length, so the bands and
 * the arithmetic behind them are the part worth pinning. Getting the
 * spoken-time estimate wrong would make the app confidently tell someone
 * their answer is a good length when it runs three minutes.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AnswerPacing from "./AnswerPacing";

const words = (n: number) => Array.from({ length: n }, (_, i) => `word${i}`).join(" ");

describe("when there is nothing to measure", () => {
  it("renders nothing for an empty answer", () => {
    const { container } = render(<AnswerPacing text="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing for whitespace", () => {
    // An expression container, not an attribute string: a backslash-n
    // inside a JSX attribute is two literal characters, not a newline,
    // which is a word as far as any whitespace split is concerned.
    const { container } = render(<AnswerPacing text={"   \n  "} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("bands", () => {
  it("treats a very short answer as room for an example", () => {
    render(<AnswerPacing text={words(20)} />);
    expect(screen.getByText(/room for a specific example/i)).toBeInTheDocument();
  });

  it("treats a normal answer as a good length", () => {
    render(<AnswerPacing text={words(120)} />);
    expect(screen.getByText(/a good length to say out loud/i)).toBeInTheDocument();
  });

  it("warns once an answer runs long", () => {
    render(<AnswerPacing text={words(300)} />);
    expect(screen.getByText(/may start skimming/i)).toBeInTheDocument();
  });
});

describe("the spoken-time estimate", () => {
  it("is about half a minute for 65 words", () => {
    // 65 words at 130 wpm is 30 seconds. If this drifts, the advice is
    // wrong in a way nobody would notice by looking at it.
    render(<AnswerPacing text={words(65)} />);
    expect(screen.getByText(/about 30s spoken/i)).toBeInTheDocument();
  });

  it("switches to minutes past a minute rather than reading 90s", () => {
    render(<AnswerPacing text={words(260)} />);
    expect(screen.getByText(/about 2 min spoken/i)).toBeInTheDocument();
  });

  it("counts words, not characters", () => {
    render(<AnswerPacing text={"  one   two \n three  "} />);
    expect(screen.getByText(/^3 words/)).toBeInTheDocument();
  });

  it("says word, singular, for one", () => {
    render(<AnswerPacing text="yes" />);
    expect(screen.getByText(/^1 word,/)).toBeInTheDocument();
  });
});
