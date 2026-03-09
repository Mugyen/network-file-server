import { useState, useEffect, useRef, useCallback } from "react";
import type { FileEntry } from "../types/files.ts";
import { searchFiles } from "../api/files.ts";

/** Debounce delay in milliseconds before firing backend search. */
const SEARCH_DEBOUNCE_MS = 300;

interface SearchState {
  query: string;
  setQuery: (q: string) => void;
  isSearching: boolean;
  searchResults: FileEntry[] | null;
  filterFiles: (files: FileEntry[]) => FileEntry[];
}

/**
 * Manages search query, debounced backend calls, and client-side filtering.
 *
 * When query is non-empty, applies instant client-side name filtering.
 * After SEARCH_DEBOUNCE_MS, fires a backend recursive search and replaces
 * results with server data. Clears state when currentPath changes.
 */
export function useSearch(currentPath: string): SearchState {
  const [query, setQueryState] = useState<string>("");
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchResults, setSearchResults] = useState<FileEntry[] | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearDebounce(): void {
    if (debounceRef.current !== null) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
  }

  // Clear query and results when path changes
  useEffect(() => {
    setQueryState("");
    setSearchResults(null);
    setIsSearching(false);
    clearDebounce();
  }, [currentPath]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => clearDebounce();
  }, []);

  function setQuery(q: string): void {
    setQueryState(q);

    if (q === "") {
      setSearchResults(null);
      setIsSearching(false);
      clearDebounce();
      return;
    }

    // Reset search results for new query (client-side fallback will kick in)
    setSearchResults(null);
    setIsSearching(true);
    clearDebounce();

    debounceRef.current = setTimeout(() => {
      void performSearch(q, currentPath);
    }, SEARCH_DEBOUNCE_MS);
  }

  async function performSearch(q: string, path: string): Promise<void> {
    try {
      const result = await searchFiles(q, path);
      setSearchResults(result.entries);
    } catch {
      // On search failure, keep client-side filtering active
      setSearchResults(null);
    } finally {
      setIsSearching(false);
    }
  }

  const filterFiles = useCallback(
    (files: FileEntry[]): FileEntry[] => {
      if (query === "") {
        return files;
      }

      // If backend search completed, return those results directly
      if (searchResults !== null) {
        return searchResults;
      }

      // Client-side fallback while debouncing/fetching
      const lowerQuery = query.toLowerCase();
      return files.filter((file) =>
        file.name.toLowerCase().includes(lowerQuery)
      );
    },
    [query, searchResults],
  );

  return { query, setQuery, isSearching, searchResults, filterFiles };
}
