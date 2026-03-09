import { useCallback, useEffect, useRef, useState } from "react";
import { uploadWithProgress, ApiError } from "../api/client.ts";
import {
  ConflictAction,
  UploadStatus,
  type UploadFileState,
} from "../types/upload.ts";

/** Maximum number of simultaneous uploads. */
const MAX_CONCURRENT = 3;

/** HTTP status code indicating a file name conflict on the server. */
const HTTP_CONFLICT = 409;

/** Monotonically increasing counter for generating unique upload IDs.
 *  crypto.randomUUID() is unavailable in non-secure contexts (HTTP + LAN IP),
 *  which is the primary use case for a WiFi file server. */
let nextUploadId = 0;

function generateUploadId(): string {
  nextUploadId += 1;
  return `upload-${String(Date.now())}-${String(nextUploadId)}`;
}

interface UseUploadResult {
  uploadFiles: (files: FileList) => void;
  uploads: UploadFileState[];
  pendingConflict: UploadFileState | null;
  resolveConflict: (action: ConflictAction) => void;
  clearCompleted: () => void;
  retryFailed: (id: string) => void;
  isUploading: boolean;
  collapsed: boolean;
  toggleCollapsed: () => void;
}

/**
 * Hook orchestrating file uploads with XHR progress, conflict handling,
 * concurrency limit (3 simultaneous), and retry support.
 */
export function useUpload(
  currentPath: string,
  onUploadComplete: () => void,
): UseUploadResult {
  const [uploads, setUploads] = useState<UploadFileState[]>([]);
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const activeCount = useRef<number>(0);
  /** IDs currently being processed — prevents duplicate processUpload calls
   *  caused by React StrictMode double-firing effects. */
  const processingIds = useRef<Set<string>>(new Set());

  const updateUpload = useCallback(
    (id: string, patch: Partial<UploadFileState>): void => {
      setUploads((prev) =>
        prev.map((u) => (u.id === id ? { ...u, ...patch } : u)),
      );
    },
    [],
  );

  const processUpload = useCallback(
    async (entry: UploadFileState): Promise<void> => {
      if (processingIds.current.has(entry.id)) {
        return;
      }
      processingIds.current.add(entry.id);
      activeCount.current += 1;
      updateUpload(entry.id, {
        status: UploadStatus.UPLOADING,
        progress: 0,
        error: null,
      });

      try {
        await uploadWithProgress(
          entry.file,
          currentPath,
          entry.conflictAction,
          (percent: number) => {
            updateUpload(entry.id, { progress: percent });
          },
        );
        updateUpload(entry.id, {
          status: UploadStatus.DONE,
          progress: 100,
        });
        onUploadComplete();
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === HTTP_CONFLICT) {
          updateUpload(entry.id, {
            status: UploadStatus.CONFLICT,
            error: "File already exists",
          });
        } else {
          const message =
            err instanceof Error ? err.message : "Upload failed";
          updateUpload(entry.id, {
            status: UploadStatus.FAILED,
            error: message,
          });
        }
      } finally {
        processingIds.current.delete(entry.id);
        activeCount.current -= 1;
      }
    },
    [currentPath, onUploadComplete, updateUpload],
  );

  /**
   * Process queued uploads whenever state changes.
   * Picks QUEUED entries while under the concurrency limit.
   */
  useEffect(() => {
    const queued = uploads.filter(
      (u) => u.status === UploadStatus.QUEUED,
    );
    const slotsAvailable = MAX_CONCURRENT - activeCount.current;

    if (slotsAvailable <= 0 || queued.length === 0) {
      return;
    }

    const toProcess = queued.slice(0, slotsAvailable);
    for (const entry of toProcess) {
      void processUpload(entry);
    }
  }, [uploads, processUpload]);

  const uploadFiles = useCallback((files: FileList): void => {
    const newEntries: UploadFileState[] = Array.from(files).map(
      (file): UploadFileState => ({
        id: generateUploadId(),
        file,
        status: UploadStatus.QUEUED,
        progress: 0,
        error: null,
        conflictAction: null,
      }),
    );
    setUploads((prev) => [...prev, ...newEntries]);
  }, []);

  const pendingConflict =
    uploads.find((u) => u.status === UploadStatus.CONFLICT) ?? null;

  const resolveConflict = useCallback(
    (action: ConflictAction): void => {
      if (pendingConflict === null) {
        throw new Error("No pending conflict to resolve");
      }

      if (action === ConflictAction.SKIP) {
        updateUpload(pendingConflict.id, {
          status: UploadStatus.DONE,
          conflictAction: action,
          error: null,
          progress: 100,
        });
        return;
      }

      // Re-queue with chosen conflict resolution
      updateUpload(pendingConflict.id, {
        status: UploadStatus.QUEUED,
        conflictAction: action,
        error: null,
        progress: 0,
      });
    },
    [pendingConflict, updateUpload],
  );

  const clearCompleted = useCallback((): void => {
    setUploads((prev) =>
      prev.filter(
        (u) =>
          u.status !== UploadStatus.DONE,
      ),
    );
  }, []);

  const retryFailed = useCallback(
    (id: string): void => {
      updateUpload(id, {
        status: UploadStatus.QUEUED,
        error: null,
        progress: 0,
        conflictAction: null,
      });
    },
    [updateUpload],
  );

  const isUploading = uploads.some(
    (u) =>
      u.status === UploadStatus.UPLOADING ||
      u.status === UploadStatus.QUEUED,
  );

  const toggleCollapsed = useCallback((): void => {
    setCollapsed((prev) => !prev);
  }, []);

  return {
    uploadFiles,
    uploads,
    pendingConflict,
    resolveConflict,
    clearCompleted,
    retryFailed,
    isUploading,
    collapsed,
    toggleCollapsed,
  };
}
