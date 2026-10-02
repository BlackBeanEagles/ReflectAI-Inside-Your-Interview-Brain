import { describe, expect, it } from "vitest";

import { highlightSegments } from "./highlight";

const marked = (text: string, kws: string[]) =>
  highlightSegments(text, kws)
    .filter((s) => s.match)
    .map((s) => s.text);

describe("highlightSegments", () => {
  it("marks a plain keyword", () => {
    expect(marked("Built APIs in Python.", ["python"])).toEqual(["Python"]);
  });

  it("is case-insensitive but returns the text as written", () => {
    expect(marked("POSTGRESQL and postgresql", ["PostgreSQL"])).toEqual(["POSTGRESQL", "postgresql"]);
  });

  it("handles keywords full of regex metacharacters", () => {
    expect(marked("C++ and Node.js, with CI/CD.", ["C++", "Node.js", "CI/CD"])).toEqual([
      "C++",
      "Node.js",
      "CI/CD",
    ]);
  });

  it("does not need a word character after the keyword, unlike \\b", () => {
    // /\bC\+\+\b/ never matches "C++ developer" -- the case this exists for.
    expect(marked("Senior C++ developer", ["C++"])).toEqual(["C++"]);
  });

  it("does not match inside a longer word", () => {
    expect(marked("JavaScript developer", ["Java"])).toEqual([]);
    expect(marked("Gopher", ["Go"])).toEqual([]);
  });

  it("prefers the longer keyword when they overlap", () => {
    expect(marked("React Native and React", ["React", "React Native"])).toEqual([
      "React Native",
      "React",
    ]);
  });

  it("reassembles to exactly the original text", () => {
    const text = "Python, C++ and React Native.\nShipped CI/CD.";
    const joined = highlightSegments(text, ["python", "c++", "react native", "ci/cd"])
      .map((s) => s.text)
      .join("");
    expect(joined).toBe(text);
  });

  it("returns the whole text unmarked when there are no keywords", () => {
    expect(highlightSegments("hello", [])).toEqual([{ text: "hello", match: false }]);
  });

  it("ignores blank keywords instead of matching everything", () => {
    expect(marked("hello world", ["", "  "])).toEqual([]);
  });

  it("returns nothing for empty text", () => {
    expect(highlightSegments("", ["python"])).toEqual([]);
  });
});

describe("phrases", () => {
  it("matches a two-word phrase split by a line break or extra spaces", () => {
    expect(marked("event\nsourcing and event   sourcing", ["event sourcing"])).toEqual([
      "event\nsourcing",
      "event   sourcing",
    ]);
  });
});
