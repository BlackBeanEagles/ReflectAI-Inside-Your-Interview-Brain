/**
 * Storage must never take a flow down with it.
 *
 * Auth used to call setItem before either setState, so a private window
 * or a full quota threw after the API had already issued a valid token:
 * the user saw "login failed" while holding working credentials, and
 * retrying just minted another. These accessors exist so that cannot
 * happen again, which means the thing worth testing is specifically that
 * they swallow rather than what they return on the happy path.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import * as storage from "./safe-storage";

function breakStorage(method: "getItem" | "setItem" | "removeItem") {
  vi.spyOn(Storage.prototype, method).mockImplementation(() => {
    throw new DOMException("blocked", "SecurityError");
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("when storage works", () => {
  it("round-trips an object", () => {
    storage.writeJson("k", { a: 1 });
    expect(storage.readJson<{ a: number }>("k")).toEqual({ a: 1 });
  });

  it("round-trips a string", () => {
    storage.writeString("s", "dark");
    expect(storage.readString("s")).toBe("dark");
  });

  it("reports a successful write", () => {
    expect(storage.writeJson("k", { a: 1 })).toBe(true);
  });

  it("returns null for a key that was never set", () => {
    expect(storage.readJson("missing")).toBeNull();
  });
});

describe("when storage throws", () => {
  it("readJson returns null instead of propagating", () => {
    breakStorage("getItem");
    expect(() => storage.readJson("k")).not.toThrow();
    expect(storage.readJson("k")).toBeNull();
  });

  it("writeJson reports failure instead of propagating", () => {
    breakStorage("setItem");
    let result: boolean | undefined;
    expect(() => {
      result = storage.writeJson("k", { a: 1 });
    }).not.toThrow();
    expect(result).toBe(false);
  });

  it("remove stays silent", () => {
    breakStorage("removeItem");
    expect(() => storage.remove("k")).not.toThrow();
  });

  it("readString returns null", () => {
    breakStorage("getItem");
    expect(storage.readString("k")).toBeNull();
  });

  it("writeString reports failure", () => {
    breakStorage("setItem");
    expect(storage.writeString("k", "v")).toBe(false);
  });
});

describe("when the stored value is corrupt", () => {
  it("readJson treats unparseable JSON as nothing to restore", () => {
    // A half-written value from a tab that was closed mid-write, or a key
    // left behind by an older version of the app.
    localStorage.setItem("k", "{not json");
    expect(storage.readJson("k")).toBeNull();
  });
});
