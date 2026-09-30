/**
 * One answer must produce exactly one feedback row.
 *
 * The first version posted on the "off the mark" click and posted again
 * when a note was added, so every complaint that bothered to explain
 * itself was counted twice -- in precisely the number this component
 * exists to produce, and biased toward the most useful responses.
 *
 * The fix moved the request later, which made the unmount flush
 * load-bearing: a verdict chosen without a note is only ever recorded by
 * the cleanup. That path fires invisibly, and when I checked it by hand
 * the first attempt read the counter before the flush had run and showed
 * zero. Nothing about it is observable in the UI, so it needs a test.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import ScoreVerdict from "./ScoreVerdict";

const PROPS = {
  sessionId: "session-1",
  question: "Tell me about the inventory service.",
  round: "technical",
  score: 4.5,
  token: null,
};

let send: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  send = vi
    .spyOn(api, "sendAnswerFeedback")
    .mockResolvedValue({ success: true, stored: true, message: "" });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("a fair verdict", () => {
  it("is sent straight away, since there is nothing to add", async () => {
    render(<ScoreVerdict {...PROPS} />);
    await userEvent.click(screen.getByRole("button", { name: /fair/i }));

    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(send.mock.calls[0][0]).toMatchObject({ verdict: "fair", session_id: "session-1" });
  });

  it("offers no note box", async () => {
    render(<ScoreVerdict {...PROPS} />);
    await userEvent.click(screen.getByRole("button", { name: /fair/i }));

    expect(screen.queryByPlaceholderText(/what did it miss/i)).not.toBeInTheDocument();
  });
});

describe("an unfair verdict", () => {
  it("does not send on the click -- it waits for the note", async () => {
    render(<ScoreVerdict {...PROPS} />);
    await userEvent.click(screen.getByRole("button", { name: /off the mark/i }));

    expect(screen.getByPlaceholderText(/what did it miss/i)).toBeInTheDocument();
    expect(send).not.toHaveBeenCalled();
  });

  it("sends exactly once when the note is submitted", async () => {
    render(<ScoreVerdict {...PROPS} />);
    await userEvent.click(screen.getByRole("button", { name: /off the mark/i }));
    await userEvent.type(
      screen.getByPlaceholderText(/what did it miss/i),
      "It ignored the trade-off I gave.",
    );
    await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(send.mock.calls[0][0]).toMatchObject({
      verdict: "unfair",
      note: "It ignored the trade-off I gave.",
    });
  });

  it("is still recorded when the user moves on without writing a note", async () => {
    // The flush. Unmounting is what "Next question" does to this component.
    const { unmount } = render(<ScoreVerdict {...PROPS} />);
    await userEvent.click(screen.getByRole("button", { name: /off the mark/i }));
    expect(send).not.toHaveBeenCalled();

    unmount();

    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(send.mock.calls[0][0]).toMatchObject({ verdict: "unfair" });
    expect(send.mock.calls[0][0].note).toBeUndefined();
  });

  it("does not send twice when a note was submitted and the component then unmounts", async () => {
    // The original bug, from the other direction: the flush must not fire
    // for a verdict that has already gone out.
    const { unmount } = render(<ScoreVerdict {...PROPS} />);
    await userEvent.click(screen.getByRole("button", { name: /off the mark/i }));
    await userEvent.type(screen.getByPlaceholderText(/what did it miss/i), "Missed the point.");
    await userEvent.click(screen.getByRole("button", { name: /^send$/i }));
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));

    unmount();

    // Give any stray cleanup a chance to fire before asserting.
    await new Promise((r) => setTimeout(r, 20));
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("sends a typed-but-unsubmitted note rather than dropping it", async () => {
    const { unmount } = render(<ScoreVerdict {...PROPS} />);
    await userEvent.click(screen.getByRole("button", { name: /off the mark/i }));
    await userEvent.type(screen.getByPlaceholderText(/what did it miss/i), "Half-written thought");

    unmount();

    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(send.mock.calls[0][0]).toMatchObject({ note: "Half-written thought" });
  });
});

describe("edge cases", () => {
  it("sends nothing at all if the user never answers the question", async () => {
    const { unmount } = render(<ScoreVerdict {...PROPS} />);
    unmount();
    await new Promise((r) => setTimeout(r, 20));
    expect(send).not.toHaveBeenCalled();
  });

  it("does not post without a session id", async () => {
    render(<ScoreVerdict {...PROPS} sessionId={null} />);
    await userEvent.click(screen.getByRole("button", { name: /fair/i }));
    await new Promise((r) => setTimeout(r, 20));
    expect(send).not.toHaveBeenCalled();
  });

  it("acknowledges the user even when the request fails", async () => {
    // A rating is never worth an error banner mid-interview.
    send.mockRejectedValue(new Error("network"));
    render(<ScoreVerdict {...PROPS} />);
    await userEvent.click(screen.getByRole("button", { name: /fair/i }));

    expect(await screen.findByText(/thanks/i)).toBeInTheDocument();
  });
});
