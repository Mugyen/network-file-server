import { useCallback, useEffect, useRef, useState } from "react";
import type { Snippet } from "../types/clipboard.ts";
import { WSMessageType } from "../types/websocket.ts";
import {
  isSnippetDeletedPayload,
  isSnippetPayload,
} from "../utils/wsGuards.ts";
import {
  fetchSnippets,
  createSnippet,
  updateSnippetTitle,
  deleteSnippet,
} from "../api/clipboard.ts";

interface UseClipboardResult {
  snippets: Snippet[];
  isOpen: boolean;
  isLoading: boolean;
  togglePanel: () => void;
  addSnippet: () => void;
  updateContent: (snippetId: string, content: string) => void;
  updateTitle: (snippetId: string, title: string) => void;
  removeSnippet: (snippetId: string) => void;
}

/** Debounce delay for WS content updates in milliseconds. */
const DEBOUNCE_MS = 300;

export function useClipboard(
  addMessageHandler: (type: string, handler: (data: unknown) => void) => void,
  removeMessageHandler: (type: string) => void,
  sendMessage: (msg: object) => void,
  onError: (message: string) => void,
): UseClipboardResult {
  const [snippets, setSnippets] = useState<Snippet[]>([]);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  // Starts true: the mount-time load below is already in flight by the time
  // anything can read this flag, so initializing avoids a setState-in-effect.
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const debounceTimers = useRef<Map<string, number>>(new Map());

  // Load snippets on mount
  useEffect(() => {
    fetchSnippets()
      .then((data) => {
        setSnippets(data);
      })
      .catch((err: unknown) => {
        // Background load — no user action to attach a toast to, but the
        // failure must not vanish: snippets will also sync via WS later.
        console.error("Failed to load clipboard snippets:", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  // Register WS handlers
  useEffect(() => {
    // Snapshot the timers map so the cleanup below clears the timers that
    // belong to this effect run, not whatever the ref points to later.
    const timers = debounceTimers.current;

    addMessageHandler(WSMessageType.SNIPPET_CREATED, (data: unknown) => {
      if (!isSnippetPayload(data)) {
        console.error("Malformed WS message", WSMessageType.SNIPPET_CREATED, data);
        return;
      }
      const payload = data;
      setSnippets((prev) => {
        // Avoid duplicates if we created it locally
        if (prev.some((s) => s.id === payload.snippet.id)) {
          return prev;
        }
        return [...prev, payload.snippet];
      });
    });

    addMessageHandler(WSMessageType.SNIPPET_UPDATED, (data: unknown) => {
      if (!isSnippetPayload(data)) {
        console.error("Malformed WS message", WSMessageType.SNIPPET_UPDATED, data);
        return;
      }
      const payload = data;
      setSnippets((prev) =>
        prev.map((s) => (s.id === payload.snippet.id ? payload.snippet : s)),
      );
    });

    addMessageHandler(WSMessageType.SNIPPET_DELETED, (data: unknown) => {
      if (!isSnippetDeletedPayload(data)) {
        console.error("Malformed WS message", WSMessageType.SNIPPET_DELETED, data);
        return;
      }
      const payload = data;
      setSnippets((prev) => prev.filter((s) => s.id !== payload.snippet_id));
    });

    return () => {
      removeMessageHandler(WSMessageType.SNIPPET_CREATED);
      removeMessageHandler(WSMessageType.SNIPPET_UPDATED);
      removeMessageHandler(WSMessageType.SNIPPET_DELETED);
      // Clear all debounce timers
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
    };
  }, [addMessageHandler, removeMessageHandler]);

  const togglePanel = useCallback((): void => {
    setIsOpen((prev) => !prev);
  }, []);

  const addSnippet = useCallback((): void => {
    createSnippet("Untitled")
      .then((snippet) => {
        setSnippets((prev) => {
          if (prev.some((s) => s.id === snippet.id)) {
            return prev;
          }
          return [...prev, snippet];
        });
      })
      .catch((err: unknown) => {
        console.error("Failed to create snippet:", err);
        onError("Couldn't create snippet");
      });
  }, [onError]);

  const updateContent = useCallback(
    (snippetId: string, content: string): void => {
      // Optimistic local update
      setSnippets((prev) =>
        prev.map((s) => (s.id === snippetId ? { ...s, content } : s)),
      );

      // Debounced WS send
      const existing = debounceTimers.current.get(snippetId);
      if (existing !== undefined) {
        clearTimeout(existing);
      }
      const timer = window.setTimeout(() => {
        sendMessage({
          type: WSMessageType.SNIPPET_UPDATE,
          snippet_id: snippetId,
          content,
        });
        debounceTimers.current.delete(snippetId);
      }, DEBOUNCE_MS);
      debounceTimers.current.set(snippetId, timer);
    },
    [sendMessage],
  );

  const updateTitle = useCallback(
    (snippetId: string, title: string): void => {
      // Optimistic update; capture the previous snippet for rollback.
      let previous: Snippet | undefined;
      setSnippets((prev) => {
        previous = prev.find((s) => s.id === snippetId);
        return prev.map((s) => (s.id === snippetId ? { ...s, title } : s));
      });
      updateSnippetTitle(snippetId, title).catch((err: unknown) => {
        console.error("Failed to update snippet title:", err);
        const rollback = previous;
        if (rollback !== undefined) {
          setSnippets((cur) =>
            cur.map((s) => (s.id === snippetId ? rollback : s)),
          );
        }
        onError("Couldn't save snippet title");
      });
    },
    [onError],
  );

  const removeSnippet = useCallback(
    (snippetId: string): void => {
      // Optimistic removal; capture the removed snippet for rollback.
      let removed: Snippet | undefined;
      setSnippets((prev) => {
        removed = prev.find((s) => s.id === snippetId);
        return prev.filter((s) => s.id !== snippetId);
      });
      deleteSnippet(snippetId).catch((err: unknown) => {
        console.error("Failed to delete snippet:", err);
        const rollback = removed;
        if (rollback !== undefined) {
          setSnippets((cur) =>
            cur.some((s) => s.id === snippetId) ? cur : [...cur, rollback],
          );
        }
        onError("Couldn't delete snippet");
      });
    },
    [onError],
  );

  return {
    snippets,
    isOpen,
    isLoading,
    togglePanel,
    addSnippet,
    updateContent,
    updateTitle,
    removeSnippet,
  };
}
