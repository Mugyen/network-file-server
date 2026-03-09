import { useCallback, useEffect, useRef, useState } from "react";
import type { Snippet } from "../types/clipboard.ts";
import { WSMessageType } from "../types/websocket.ts";
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
): UseClipboardResult {
  const [snippets, setSnippets] = useState<Snippet[]>([]);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const debounceTimers = useRef<Map<string, number>>(new Map());

  // Load snippets on mount
  useEffect(() => {
    setIsLoading(true);
    fetchSnippets()
      .then((data) => {
        setSnippets(data);
      })
      .catch(() => {
        // Silent fail -- snippets are non-critical
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  // Register WS handlers
  useEffect(() => {
    addMessageHandler(WSMessageType.SNIPPET_CREATED, (data: unknown) => {
      const payload = data as { snippet: Snippet };
      setSnippets((prev) => {
        // Avoid duplicates if we created it locally
        if (prev.some((s) => s.id === payload.snippet.id)) {
          return prev;
        }
        return [...prev, payload.snippet];
      });
    });

    addMessageHandler(WSMessageType.SNIPPET_UPDATED, (data: unknown) => {
      const payload = data as { snippet: Snippet };
      setSnippets((prev) =>
        prev.map((s) => (s.id === payload.snippet.id ? payload.snippet : s)),
      );
    });

    addMessageHandler(WSMessageType.SNIPPET_DELETED, (data: unknown) => {
      const payload = data as { snippet_id: string };
      setSnippets((prev) => prev.filter((s) => s.id !== payload.snippet_id));
    });

    return () => {
      removeMessageHandler(WSMessageType.SNIPPET_CREATED);
      removeMessageHandler(WSMessageType.SNIPPET_UPDATED);
      removeMessageHandler(WSMessageType.SNIPPET_DELETED);
      // Clear all debounce timers
      debounceTimers.current.forEach((timer) => clearTimeout(timer));
      debounceTimers.current.clear();
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
      .catch(() => {
        // Silent fail
      });
  }, []);

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
      setSnippets((prev) =>
        prev.map((s) => (s.id === snippetId ? { ...s, title } : s)),
      );
      updateSnippetTitle(snippetId, title).catch(() => {
        // Silent fail
      });
    },
    [],
  );

  const removeSnippet = useCallback((snippetId: string): void => {
    setSnippets((prev) => prev.filter((s) => s.id !== snippetId));
    deleteSnippet(snippetId).catch(() => {
      // Silent fail
    });
  }, []);

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
