import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Unmount between tests. This matters more than usual here: the component
// under test in ScoreVerdict.test.tsx does work in its unmount cleanup, so
// leaving a tree mounted would leak that work into the next test and make
// the post counts wrong in a way that looks like a product bug.
afterEach(() => {
  cleanup();
});
