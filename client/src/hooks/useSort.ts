import { useState, useCallback } from "react";
import { FileType } from "../types/files.ts";
import type { FileEntry } from "../types/files.ts";

/** Sort field options for file listing columns. */
export const SortField = {
  NAME: "name",
  SIZE: "size",
  MODIFIED: "modified",
} as const;

export type SortField = (typeof SortField)[keyof typeof SortField];

/** Sort direction options. */
export const SortDirection = {
  ASC: "asc",
  DESC: "desc",
} as const;

export type SortDirection = (typeof SortDirection)[keyof typeof SortDirection];

interface SortState {
  field: SortField;
  direction: SortDirection;
  toggleSort: (field: SortField) => void;
  sortFiles: (files: FileEntry[]) => FileEntry[];
}

/**
 * Manages column sort state with toggle behavior.
 *
 * Clicking the same column flips direction; clicking a different column
 * sets it as the active field with ASC direction.
 * sortFiles always places directories before files, then applies the
 * user-selected sort within each group.
 */
export function useSort(): SortState {
  const [field, setField] = useState<SortField>(SortField.NAME);
  const [direction, setDirection] = useState<SortDirection>(SortDirection.ASC);

  function toggleSort(clickedField: SortField): void {
    if (clickedField === field) {
      setDirection(
        direction === SortDirection.ASC ? SortDirection.DESC : SortDirection.ASC,
      );
    } else {
      setField(clickedField);
      setDirection(SortDirection.ASC);
    }
  }

  const sortFiles = useCallback(
    (files: FileEntry[]): FileEntry[] => {
      const multiplier = direction === SortDirection.ASC ? 1 : -1;

      return [...files].sort((a, b) => {
        // Directories always sort before files
        const aIsDir = a.type === FileType.DIRECTORY ? 0 : 1;
        const bIsDir = b.type === FileType.DIRECTORY ? 0 : 1;
        if (aIsDir !== bIsDir) {
          return aIsDir - bIsDir;
        }

        // Within the same group, apply user-selected sort
        switch (field) {
          case SortField.NAME:
            return multiplier * a.name.localeCompare(b.name);
          case SortField.SIZE:
            return multiplier * (a.size - b.size);
          case SortField.MODIFIED:
            return multiplier * a.modified.localeCompare(b.modified);
        }
      });
    },
    [field, direction],
  );

  return { field, direction, toggleSort, sortFiles };
}
