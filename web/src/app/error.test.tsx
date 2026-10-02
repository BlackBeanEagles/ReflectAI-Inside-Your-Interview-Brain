/**
 * The error boundary reloads by itself on a stale-chunk error. The risk in
 * that is a loop: if the server is actually down, every reload fails the
 * same way, so the automatic reload must happen at most once per window.
 */

import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RouteError from "./error";

const chunkError = () =>
  Object.assign(new Error("Failed to load chunk /_next/static/chunks/x.js"), { name: "ChunkLoadError" });

let reload: ReturnType<typeof vi.fn>;
const realLocation = window.location;

beforeEach(() => {
  reload = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...realLocation, reload },
  });
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: realLocation });
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("a stale-chunk error", () => {
  it("reloads once by itself and says so", () => {
    render(<RouteError error={chunkError()} reset={() => {}} />);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/loading the latest version/i)).toBeInTheDocument();
  });

  it("does not reload again straight away -- no loop when the server is down", () => {
    sessionStorage.setItem("reflectinterview_chunk_reload_at", String(Date.now()));
    render(<RouteError error={chunkError()} reset={() => {}} />);
    expect(reload).not.toHaveBeenCalled();
    expect(screen.getByText(/couldn't finish loading/i)).toBeInTheDocument();
  });

  it("offers a real reload, not reset(), once it has given up", () => {
    // reset() re-renders with the same stale chunk map and cannot help.
    sessionStorage.setItem("reflectinterview_chunk_reload_at", String(Date.now()));
    const reset = vi.fn();
    render(<RouteError error={chunkError()} reset={reset} />);
    screen.getByRole("button", { name: /reload/i }).click();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(reset).not.toHaveBeenCalled();
  });

  it("reloads again for a later deploy, once the window has passed", () => {
    sessionStorage.setItem("reflectinterview_chunk_reload_at", String(Date.now() - 60_000));
    render(<RouteError error={chunkError()} reset={() => {}} />);
    expect(reload).toHaveBeenCalledTimes(1);
  });
});

describe("any other error", () => {
  it("never reloads, and offers reset", () => {
    const reset = vi.fn();
    render(<RouteError error={new Error("Cannot read properties of undefined")} reset={reset} />);
    expect(reload).not.toHaveBeenCalled();
    screen.getByRole("button", { name: /try again/i }).click();
    expect(reset).toHaveBeenCalledTimes(1);
  });
});
