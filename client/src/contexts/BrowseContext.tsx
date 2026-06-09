import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactElement, ReactNode } from "react";
import type { FileEntry } from "../types/files.ts";
import { FileType } from "../types/files.ts";
import { FileCategory, getFileCategory } from "../types/fileCategories.ts";
import {
  fetchFiles,
  downloadFile,
  downloadAsZip,
  deleteFiles,
  renameFile,
  createFolder,
} from "../api/files.ts";
import { usePathNavigation } from "../hooks/usePathNavigation.ts";
import { useSearch } from "../hooks/useSearch.ts";
import { useSort } from "../hooks/useSort.ts";
import { useFileSelection } from "../hooks/useFileSelection.ts";
import { usePreview } from "../hooks/usePreview.ts";

interface BrowseContextValue {
  /** Raw directory listing for the current path. */
  files: FileEntry[];
  /** Listing after the search -> category filter -> sort pipeline. */
  sortedFiles: FileEntry[];
  loading: boolean;
  error: string | null;
  /** Surface an operation failure in the browse error banner. */
  reportError: (message: string) => void;
  loadFiles: () => Promise<void>;
  currentPath: string;
  navigateTo: (path: string) => void;
  search: ReturnType<typeof useSearch>;
  sort: ReturnType<typeof useSort>;
  selection: ReturnType<typeof useFileSelection>;
  preview: ReturnType<typeof usePreview>;
  activeCategories: Set<FileCategory>;
  toggleCategory: (category: FileCategory) => void;
  /** Trigger a direct browser download for a single file path. */
  downloadPath: (path: string) => void;
  /** Download the current selection as a ZIP archive. */
  downloadZipSelected: () => Promise<void>;
  /** Delete the current selection, clear it, and reload the listing. */
  deleteSelected: () => Promise<void>;
  /** Delete a single path and reload the listing. */
  deletePath: (path: string) => Promise<void>;
  renamePath: (path: string, newName: string) => Promise<void>;
  /** Create a folder inside the current path and reload the listing. */
  createFolderInCurrent: (name: string) => Promise<void>;
}

const BrowseContext = createContext<BrowseContextValue | null>(null);

interface BrowseProviderProps {
  children: ReactNode;
}

/**
 * Owns the file-browsing slice: listing state, path navigation, search,
 * category filters, sorting, selection, preview, and the file operations
 * that report failures through the shared browse error banner.
 */
export function BrowseProvider({ children }: BrowseProviderProps): ReactElement {
  const { currentPath, navigateTo } = usePathNavigation();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const search = useSearch(currentPath);
  const sort = useSort();
  const preview = usePreview(currentPath);
  const selection = useFileSelection(files);

  // Category filter state
  const [activeCategories, setActiveCategories] = useState<Set<FileCategory>>(
    () => new Set([FileCategory.ALL]),
  );

  const loadFiles = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const listing = await fetchFiles(currentPath);
      setFiles(listing.entries);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load files";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [currentPath]);

  // Reload file listing when path changes
  useEffect(() => {
    void loadFiles();
  }, [loadFiles]);

  const reportError = useCallback((message: string): void => {
    setError(message);
  }, []);

  // --- Category filter ---

  function toggleCategory(category: FileCategory): void {
    if (category === FileCategory.ALL) {
      setActiveCategories(new Set([FileCategory.ALL]));
      return;
    }

    setActiveCategories((prev) => {
      const next = new Set(prev);
      next.delete(FileCategory.ALL);

      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }

      // If nothing is selected, re-activate ALL
      if (next.size === 0) {
        next.add(FileCategory.ALL);
      }
      return next;
    });
  }

  // --- File pipeline: search -> category filter -> sort ---

  const filteredBySearch = search.filterFiles(files);
  const filteredByCategory = activeCategories.has(FileCategory.ALL)
    ? filteredBySearch
    : filteredBySearch.filter(
        (f) =>
          f.type === FileType.DIRECTORY ||
          activeCategories.has(getFileCategory(f.name)),
      );
  const sortedFiles = sort.sortFiles(filteredByCategory);

  // --- Batch operations ---

  function buildSelectedPaths(): string[] {
    return Array.from(selection.selectedNames).map((name) =>
      currentPath === "" ? name : currentPath + "/" + name,
    );
  }

  async function downloadZipSelected(): Promise<void> {
    try {
      await downloadAsZip(buildSelectedPaths());
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "ZIP download failed";
      setError(message);
    }
  }

  async function deleteSelected(): Promise<void> {
    try {
      await deleteFiles(buildSelectedPaths());
      selection.clearSelection();
      await loadFiles();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Delete failed";
      setError(message);
    }
  }

  // --- Single-file operations ---

  async function deletePath(path: string): Promise<void> {
    try {
      await deleteFiles([path]);
      await loadFiles();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Delete failed";
      setError(message);
    }
  }

  async function renamePath(path: string, newName: string): Promise<void> {
    try {
      await renameFile(path, newName);
      await loadFiles();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Rename failed";
      setError(message);
    }
  }

  function downloadPath(path: string): void {
    downloadFile(path);
  }

  async function createFolderInCurrent(name: string): Promise<void> {
    try {
      await createFolder(currentPath, name);
      await loadFiles();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Create folder failed";
      setError(message);
    }
  }

  const value: BrowseContextValue = {
    files,
    sortedFiles,
    loading,
    error,
    reportError,
    loadFiles,
    currentPath,
    navigateTo,
    search,
    sort,
    selection,
    preview,
    activeCategories,
    toggleCategory,
    downloadPath,
    downloadZipSelected,
    deleteSelected,
    deletePath,
    renamePath,
    createFolderInCurrent,
  };

  return <BrowseContext.Provider value={value}>{children}</BrowseContext.Provider>;
}

/**
 * Consumer hook for the file-browsing slice.
 * Throws if called outside a BrowseProvider (strict contract).
 */
// eslint-disable-next-line react-refresh/only-export-components -- provider and its consumer hook are intentionally co-located; fast refresh falls back to a full reload here.
export function useBrowse(): BrowseContextValue {
  const value = useContext(BrowseContext);
  if (value === null) {
    throw new Error("useBrowse must be used within a BrowseProvider");
  }
  return value;
}
