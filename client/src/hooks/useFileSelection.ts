import { useCallback, useState } from "react";
import type { FileEntry } from "../types/files.ts";

interface FileSelectionResult {
  selectedNames: Set<string>;
  isAllSelected: boolean;
  isIndeterminate: boolean;
  toggleSelect: (name: string) => void;
  toggleSelectAll: () => void;
  clearSelection: () => void;
  selectedCount: number;
}

/**
 * Manages checkbox selection state for file list items.
 * Supports select-all with indeterminate state, per-item toggle, and
 * auto-clears when the file listing changes (e.g. navigating directories).
 */
export function useFileSelection(files: FileEntry[]): FileSelectionResult {
  const [selectedNames, setSelectedNames] = useState<Set<string>>(new Set());

  // Reset selection when files change (new directory navigation) using the
  // adjust-state-during-render pattern instead of a setState-in-effect
  // (https://react.dev/learn/you-might-not-need-an-effect).
  const [prevFiles, setPrevFiles] = useState<FileEntry[]>(files);
  if (files !== prevFiles) {
    setPrevFiles(files);
    setSelectedNames(new Set());
  }

  const toggleSelect = useCallback((name: string): void => {
    setSelectedNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback((): void => {
    setSelectedNames((prev) => {
      const allSelected = prev.size === files.length && files.length > 0;
      if (allSelected) {
        return new Set();
      }
      return new Set(files.map((f) => f.name));
    });
  }, [files]);

  const clearSelection = useCallback((): void => {
    setSelectedNames(new Set());
  }, []);

  const isAllSelected = selectedNames.size === files.length && files.length > 0;
  const isIndeterminate =
    selectedNames.size > 0 && selectedNames.size < files.length;
  const selectedCount = selectedNames.size;

  return {
    selectedNames,
    isAllSelected,
    isIndeterminate,
    toggleSelect,
    toggleSelectAll,
    clearSelection,
    selectedCount,
  };
}
