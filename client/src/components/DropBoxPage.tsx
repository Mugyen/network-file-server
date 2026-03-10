import { useCallback, useEffect, useRef, useState } from "react";
import { CloudUpload, Check } from "lucide-react";
import { useUpload } from "../hooks/useUpload.ts";
import { useDragDrop } from "../hooks/useDragDrop.ts";
import { useTheme, ThemeMode } from "../hooks/useTheme.ts";
import { useToast } from "../hooks/useToast.ts";
import { UploadStatus } from "../types/upload.ts";
import ThemeToggle from "./ThemeToggle.tsx";
import UploadPanel from "./UploadPanel.tsx";
import ConflictDialog from "./ConflictDialog.tsx";
import ToastContainer from "./ToastContainer.tsx";

interface DropBoxPageProps {
  hostname: string;
}

interface CompletedFile {
  name: string;
  size: string;
}

/** Format bytes into human-readable size string. */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${String(bytes)} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

/** Cycle order for theme toggle: SYSTEM -> DARK -> LIGHT -> SYSTEM */
function cycleThemeMode(current: ThemeMode): ThemeMode {
  switch (current) {
    case ThemeMode.SYSTEM:
      return ThemeMode.DARK;
    case ThemeMode.DARK:
      return ThemeMode.LIGHT;
    case ThemeMode.LIGHT:
      return ThemeMode.SYSTEM;
  }
}

function DropBoxPage({ hostname }: DropBoxPageProps) {
  const [completedFiles, setCompletedFiles] = useState<CompletedFile[]>([]);
  const theme = useTheme();
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  /** Track which upload IDs we have already recorded as completed. */
  const recordedIdsRef = useRef<Set<string>>(new Set());

  const handleUploadComplete = useCallback(async (): Promise<void> => {
    // No-op: we track completed files via upload state monitoring below
    await Promise.resolve();
  }, []);

  const upload = useUpload("", handleUploadComplete);
  const { isDragging, dragHandlers } = useDragDrop(upload.uploadFiles);

  // Monitor upload state to detect newly completed files
  useEffect(() => {
    for (const u of upload.uploads) {
      if (u.status === UploadStatus.DONE && !recordedIdsRef.current.has(u.id)) {
        recordedIdsRef.current.add(u.id);
        setCompletedFiles((prev) => [
          ...prev,
          { name: u.file.name, size: formatFileSize(u.file.size) },
        ]);
      }
    }
  }, [upload.uploads]);

  function handleChooseFiles(): void {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const files = e.target.files;
    if (files !== null && files.length > 0) {
      upload.uploadFiles(files);
    }
    e.target.value = "";
  }

  function handleThemeToggle(): void {
    theme.setMode(cycleThemeMode(theme.mode));
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900" {...dragHandlers}>
      {/* Header */}
      <header className="py-6">
        <div className="container mx-auto max-w-2xl px-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100 truncate">
            {hostname}
          </h1>
          <ThemeToggle
            mode={theme.mode}
            isDark={theme.isDark}
            onToggle={handleThemeToggle}
          />
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto max-w-2xl px-4 py-8">
        {/* Drop zone */}
        <div
          className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
            isDragging
              ? "border-blue-400 bg-blue-50 dark:border-blue-500 dark:bg-blue-900/20"
              : "border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
          }`}
        >
          <CloudUpload
            className={`h-16 w-16 mx-auto mb-4 ${
              isDragging
                ? "text-blue-500 dark:text-blue-400"
                : "text-gray-400 dark:text-gray-500"
            }`}
          />
          <p className="text-lg font-medium text-gray-700 dark:text-gray-200 mb-1">
            Drop files here
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            or use the button below to browse
          </p>
          <button
            type="button"
            onClick={handleChooseFiles}
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Choose files...
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {/* Completed files list */}
        {completedFiles.length > 0 && (
          <div className="mt-6 space-y-2">
            <h2 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
              Uploaded files
            </h2>
            {completedFiles.map((file, index) => (
              <div
                key={`${file.name}-${String(index)}`}
                className="flex items-center gap-2 py-1.5 px-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
              >
                <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                <span className="text-sm text-gray-700 dark:text-gray-200 truncate flex-1">
                  {file.name}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
                  {file.size}
                </span>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Upload panel -- floating bottom-right */}
      <UploadPanel
        uploads={upload.uploads}
        collapsed={upload.collapsed}
        onToggleCollapse={upload.toggleCollapsed}
        onClearCompleted={upload.clearCompleted}
        onRetry={upload.retryFailed}
      />

      {/* Conflict dialog */}
      {upload.pendingConflict !== null && (
        <ConflictDialog
          fileName={upload.pendingConflict.file.name}
          onResolve={upload.resolveConflict}
        />
      )}

      {/* Toast notifications */}
      <ToastContainer
        toasts={toast.visibleToasts}
        overflowCount={toast.overflowCount}
        onDismiss={toast.dismissToast}
      />
    </div>
  );
}

export default DropBoxPage;
