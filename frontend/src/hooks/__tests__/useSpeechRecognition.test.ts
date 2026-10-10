// The live captions survive a dropped connection: a network error is retried with a back-off, and only
// after the retries are used up does the hook report it.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSpeechRecognition } from "../useSpeechRecognition";

class FakeRecognition {
  static instances: FakeRecognition[] = [];
  continuous = false;
  interimResults = false;
  lang = "";
  onresult: ((e: unknown) => void) | null = null;
  onerror: ((e: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  starts = 0;
  constructor() {
    FakeRecognition.instances.push(this);
  }
  start() {
    this.starts += 1;
  }
  stop() {}
  abort() {}
  /** Chrome fires `error` and then `end` when the speech service connection drops. */
  fail(error: string) {
    this.onerror?.({ error });
    this.onend?.();
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeRecognition.instances = [];
  (window as unknown as { webkitSpeechRecognition: unknown }).webkitSpeechRecognition = FakeRecognition;
});

afterEach(() => {
  vi.useRealTimers();
  delete (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition;
});

describe("useSpeechRecognition network errors", () => {
  it("reconnects after a dropped connection instead of giving up", () => {
    const { result } = renderHook(() => useSpeechRecognition());
    act(() => result.current.start());
    const rec = FakeRecognition.instances[0];

    act(() => rec.fail("network"));
    expect(result.current.reconnecting).toBe(true);
    expect(result.current.error).toBeNull();
    expect(rec.starts).toBe(1); // waiting out the back-off

    act(() => void vi.advanceTimersByTime(600));
    expect(rec.starts).toBe(2);

    act(() =>
      rec.onresult?.({ resultIndex: 0, results: [Object.assign([{ transcript: "hello again" }], { isFinal: true })] }),
    );
    expect(result.current.reconnecting).toBe(false);
    expect(result.current.finalText).toBe("hello again");
  });

  it("reports the failure only after the retries are used up", () => {
    const { result } = renderHook(() => useSpeechRecognition());
    act(() => result.current.start());
    const rec = FakeRecognition.instances[0];

    for (const wait of [600, 1200, 2400]) {
      act(() => rec.fail("network"));
      expect(result.current.error).toBeNull();
      act(() => void vi.advanceTimersByTime(wait));
    }
    act(() => rec.fail("network"));

    expect(result.current.errorKind).toBe("network");
    expect(result.current.error).toMatch(/lost their connection/);
    expect(result.current.reconnecting).toBe(false);
    expect(rec.starts).toBe(4); // first start plus three retries, no fifth
  });

  it("does not retry a blocked microphone", () => {
    const { result } = renderHook(() => useSpeechRecognition());
    act(() => result.current.start());
    const rec = FakeRecognition.instances[0];

    act(() => rec.fail("not-allowed"));

    expect(result.current.errorKind).toBe("blocked");
    expect(rec.starts).toBe(1);
  });
});
