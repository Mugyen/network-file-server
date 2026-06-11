// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { useWebSocket } from "./useWebSocket.ts";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

/** Minimal WebSocket stand-in: records instances and lets tests drive the
 *  open/message/close lifecycle by hand. */
class MockWebSocket {
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readonly url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readonly send = vi.fn();
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close(): void {
    this.closed = true;
    this.readyState = MockWebSocket.CLOSED;
  }

  // -- test drivers --
  triggerOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    act(() => this.onopen?.());
  }
  triggerMessage(data: unknown): void {
    act(() => this.onmessage?.({ data: JSON.stringify(data) }));
  }
  triggerClose(): void {
    this.readyState = MockWebSocket.CLOSED;
    act(() => this.onclose?.());
  }
}

function latest(): MockWebSocket {
  const ws = MockWebSocket.instances.at(-1);
  if (ws === undefined) throw new Error("no WebSocket created");
  return ws;
}

let current: ReturnType<typeof useWebSocket> | null = null;

function Harness(): null {
  const value = useWebSocket("dev-1", "Device One");
  useEffect(() => {
    current = value;
  });
  return null;
}

function hook(): ReturnType<typeof useWebSocket> {
  if (current === null) throw new Error("useWebSocket harness did not render");
  return current;
}

const BASE_DELAY = 1000;
const STABLE_MS = 3000;
const MAX_DELAY = 30000;

describe("useWebSocket", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.useFakeTimers();
    // jitter is Math.random() * MAX_JITTER — pin to 0 for exact delays.
    vi.spyOn(Math, "random").mockReturnValue(0);
    MockWebSocket.instances = [];
    current = null;
    vi.stubGlobal("WebSocket", MockWebSocket);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  function mount(): void {
    act(() => {
      root.render(<Harness />);
    });
  }

  it("opens a WebSocket on mount and reports connected on open", () => {
    mount();
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(latest().url).toContain("/ws?");
    expect(hook().isConnected).toBe(false);

    latest().triggerOpen();
    expect(hook().isConnected).toBe(true);
  });

  it("reconnects after close once the backoff delay elapses", () => {
    mount();
    latest().triggerOpen();
    latest().triggerClose();
    expect(hook().isConnected).toBe(false);

    // No reconnect before the first backoff window (BASE_DELAY).
    act(() => vi.advanceTimersByTime(BASE_DELAY - 1));
    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => vi.advanceTimersByTime(1));
    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("escalates the backoff delay on repeated close-before-stable", () => {
    mount();
    // 1st close: delay = BASE_DELAY (attempt 0).
    latest().triggerClose();
    act(() => vi.advanceTimersByTime(BASE_DELAY));
    expect(MockWebSocket.instances).toHaveLength(2);

    // 2nd close: delay = BASE_DELAY * 2 (attempt 1) — 1000ms is not enough.
    latest().triggerClose();
    act(() => vi.advanceTimersByTime(BASE_DELAY));
    expect(MockWebSocket.instances).toHaveLength(2);
    act(() => vi.advanceTimersByTime(BASE_DELAY)); // total 2000ms
    expect(MockWebSocket.instances).toHaveLength(3);

    // 3rd close: delay = BASE_DELAY * 4 (attempt 2) = 4000ms.
    latest().triggerClose();
    act(() => vi.advanceTimersByTime(3999));
    expect(MockWebSocket.instances).toHaveLength(3);
    act(() => vi.advanceTimersByTime(1));
    expect(MockWebSocket.instances).toHaveLength(4);
  });

  it("resets the backoff after a connection stays stable", () => {
    mount();
    // Escalate once.
    latest().triggerClose();
    act(() => vi.advanceTimersByTime(BASE_DELAY));
    expect(MockWebSocket.instances).toHaveLength(2);

    // This connection opens and survives past the stable threshold.
    latest().triggerOpen();
    act(() => vi.advanceTimersByTime(STABLE_MS));

    // After a stable connection, the next close starts from BASE_DELAY again.
    latest().triggerClose();
    act(() => vi.advanceTimersByTime(BASE_DELAY));
    expect(MockWebSocket.instances).toHaveLength(3);
  });

  it("caps the backoff delay at the maximum", () => {
    mount();
    // Drive the attempt counter high with rapid close-before-stable cycles.
    for (let i = 0; i < 8; i++) {
      latest().triggerClose();
      act(() => vi.advanceTimersByTime(MAX_DELAY));
    }
    const countBefore = MockWebSocket.instances.length;
    // One more close: even at a high attempt count the wait never exceeds
    // MAX_DELAY, so advancing MAX_DELAY always produces exactly one reconnect.
    latest().triggerClose();
    act(() => vi.advanceTimersByTime(MAX_DELAY));
    expect(MockWebSocket.instances.length).toBe(countBefore + 1);
  });

  it("dispatches a message to a registered handler", () => {
    mount();
    latest().triggerOpen();
    const handler = vi.fn();
    act(() => hook().addMessageHandler("custom_event", handler));

    latest().triggerMessage({ type: "custom_event", value: 42 });
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith({ type: "custom_event", value: 42 });

    // A removed handler no longer fires.
    act(() => hook().removeMessageHandler("custom_event"));
    latest().triggerMessage({ type: "custom_event", value: 7 });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("stops reconnecting after unmount", () => {
    mount();
    latest().triggerClose();
    const countAtUnmount = MockWebSocket.instances.length;

    act(() => root.unmount());
    // Any pending reconnect timer must not fire a new connection.
    act(() => vi.advanceTimersByTime(MAX_DELAY));
    expect(MockWebSocket.instances.length).toBe(countAtUnmount);
  });
});
