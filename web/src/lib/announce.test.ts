/**
 * The live-region store.
 *
 * The subtle requirement is re-announcement: if someone re-runs a scorer
 * and gets the same number back, setting identical text would leave the
 * DOM node unchanged and most screen readers would say nothing -- which
 * reads as "my click did nothing", the exact confusion this whole
 * mechanism exists to remove.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { announce, clearAnnouncement } from "./announce";

// The store defers by a frame so a clear lands as its own mutation.
const settle = () => new Promise((r) => setTimeout(r, 80));

afterEach(() => {
  clearAnnouncement();
  vi.restoreAllMocks();
});

async function currentMessage(): Promise<string> {
  const { renderHook } = await import("@testing-library/react");
  const { useAnnouncement } = await import("./announce");
  const { result } = renderHook(() => useAnnouncement());
  return result.current;
}

describe("announce", () => {
  it("publishes a message", async () => {
    announce("ATS score ready: 50 out of 100.");
    await settle();
    expect(await currentMessage()).toBe("ATS score ready: 50 out of 100.");
  });

  it("clears back to empty", async () => {
    announce("something");
    await settle();
    clearAnnouncement();
    expect(await currentMessage()).toBe("");
  });

  it("re-announces identical text by clearing first", async () => {
    const seen: string[] = [];
    announce("Scored 7.0 out of 10.");
    await settle();
    seen.push(await currentMessage());

    // Same result a second time -- without the clear this would be a
    // no-op mutation and would never be spoken.
    announce("Scored 7.0 out of 10.");
    seen.push(await currentMessage()); // mid-flight: the cleared state
    await settle();
    seen.push(await currentMessage());

    expect(seen[0]).toBe("Scored 7.0 out of 10.");
    expect(seen[1]).toBe("");
    expect(seen[2]).toBe("Scored 7.0 out of 10.");
  });

  it("notifies subscribers", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAnnouncement } = await import("./announce");
    const { result } = renderHook(() => useAnnouncement());

    expect(result.current).toBe("");
    announce("first");
    await settle();
    expect(result.current).toBe("first");
  });
});
