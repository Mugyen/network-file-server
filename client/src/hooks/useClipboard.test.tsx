// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { useClipboard } from "./useClipboard.ts";
import type { Snippet } from "../types/clipboard.ts";
import { WSMessageType } from "../types/websocket.ts";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  fetchSnippets: vi.fn(),
  createSnippet: vi.fn(),
  updateSnippetTitle: vi.fn(),
  deleteSnippet: vi.fn(),
}));

vi.mock("../api/clipboard.ts", () => mocks);

function snippet(id: string, content = "", title = "Untitled"): Snippet {
  return {
    id,
    title,
    content,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

// WS plumbing captured so tests can push messages and assert sends. The
// add/remove callbacks must be STABLE across renders (as App.tsx's
// useCallback ones are) — otherwise the hook's WS-handler effect re-runs
// every render and its cleanup clears pending debounce timers.
let wsHandlers: Map<string, (data: unknown) => void>;
let addHandler: (type: string, h: (data: unknown) => void) => void;
let removeHandler: (type: string) => void;
let sendMessage: ReturnType<typeof vi.fn>;
let onError: ReturnType<typeof vi.fn>;

let current: ReturnType<typeof useClipboard> | null = null;

function Harness(): null {
  const value = useClipboard(addHandler, removeHandler, sendMessage, onError);
  useEffect(() => {
    current = value;
  });
  return null;
}

function hook(): ReturnType<typeof useClipboard> {
  if (current === null) throw new Error("useClipboard harness did not render");
  return current;
}

function pushWs(type: string, data: unknown): void {
  const h = wsHandlers.get(type);
  if (h === undefined) throw new Error(`no handler for ${type}`);
  act(() => h(data));
}

describe("useClipboard", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.clearAllMocks();
    current = null;
    wsHandlers = new Map();
    addHandler = (type, h) => wsHandlers.set(type, h);
    removeHandler = (type) => wsHandlers.delete(type);
    sendMessage = vi.fn();
    onError = vi.fn();
    mocks.fetchSnippets.mockResolvedValue([]);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.restoreAllMocks();
  });

  async function mount(): Promise<void> {
    await act(async () => {
      root.render(<Harness />);
    });
    // Flush the mount-time fetchSnippets promise chain.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  it("loads snippets on mount and clears the loading flag", async () => {
    mocks.fetchSnippets.mockResolvedValue([snippet("a", "hi")]);
    await mount();
    expect(mocks.fetchSnippets).toHaveBeenCalledTimes(1);
    expect(hook().isLoading).toBe(false);
    expect(hook().snippets.map((s) => s.id)).toEqual(["a"]);
  });

  it("debounces content updates: rapid edits coalesce into one send with the latest value", async () => {
    mocks.fetchSnippets.mockResolvedValue([snippet("a", "")]);
    await mount();

    // Fake timers only for the debounce window (mount used real timers).
    vi.useFakeTimers();
    try {
      act(() => hook().updateContent("a", "h"));
      act(() => hook().updateContent("a", "he"));
      act(() => hook().updateContent("a", "hello"));

      // Optimistic local update is immediate.
      expect(hook().snippets[0].content).toBe("hello");
      // No send before the debounce window elapses.
      expect(sendMessage).not.toHaveBeenCalled();

      vi.advanceTimersByTime(300);

      expect(sendMessage).toHaveBeenCalledTimes(1);
      expect(sendMessage).toHaveBeenCalledWith({
        type: WSMessageType.SNIPPET_UPDATE,
        snippet_id: "a",
        content: "hello",
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it("applies a WS SNIPPET_CREATED push (and dedups already-known ids)", async () => {
    await mount();
    pushWs(WSMessageType.SNIPPET_CREATED, { snippet: snippet("x", "new") });
    expect(hook().snippets.map((s) => s.id)).toEqual(["x"]);

    // A duplicate push must not add the snippet twice.
    pushWs(WSMessageType.SNIPPET_CREATED, { snippet: snippet("x", "new") });
    expect(hook().snippets).toHaveLength(1);
  });

  it("reconciles a WS SNIPPET_UPDATED push against the local copy", async () => {
    mocks.fetchSnippets.mockResolvedValue([snippet("a", "old")]);
    await mount();
    pushWs(WSMessageType.SNIPPET_UPDATED, { snippet: snippet("a", "remote") });
    expect(hook().snippets[0].content).toBe("remote");
  });

  it("removes a snippet on a WS SNIPPET_DELETED push", async () => {
    mocks.fetchSnippets.mockResolvedValue([snippet("a"), snippet("b")]);
    await mount();
    pushWs(WSMessageType.SNIPPET_DELETED, { snippet_id: "a" });
    expect(hook().snippets.map((s) => s.id)).toEqual(["b"]);
  });

  it("rolls back an optimistic title update when the API call fails", async () => {
    mocks.fetchSnippets.mockResolvedValue([snippet("a", "", "Original")]);
    mocks.updateSnippetTitle.mockRejectedValue(new Error("nope"));
    await mount();

    act(() => hook().updateTitle("a", "Renamed"));
    // Flush the rejected updateSnippetTitle promise + the rollback setState.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(hook().snippets[0].title).toBe("Original");
    expect(onError).toHaveBeenCalledWith("Couldn't save snippet title");
  });
});
