import { CheckCircle, ChevronDown, ChevronUp, RefreshCw, X } from "lucide-react";
import { UploadStatus, type UploadFileState } from "../types/upload.ts";

interface UploadPanelProps {
  uploads: UploadFileState[];
  collapsed: boolean;
  onToggleCollapse: () => void;
  onClearCompleted: () => void;
  onRetry: (id: string) => void;
}

/** Truncate a file name to a max character length, preserving the extension. */
function truncateName(name: string, maxLen: number): string {
  if (name.length <= maxLen) {
    return name;
  }
  const ext = name.lastIndexOf(".");
  if (ext === -1) {
    return name.slice(0, maxLen - 3) + "...";
  }
  const extension = name.slice(ext);
  const base = name.slice(0, maxLen - extension.length - 3);
  return base + "..." + extension;
}

/** Render a single upload item row. */
function UploadItem({
  upload,
  onRetry,
}: {
  upload: UploadFileState;
  onRetry: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 border-t border-gray-100">
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-700 truncate" title={upload.file.name}>
          {truncateName(upload.file.name, 30)}
        </p>

        {upload.status === UploadStatus.UPLOADING && (
          <div className="mt-1 h-1.5 w-full rounded-full bg-gray-200">
            <div
              className="h-1.5 rounded-full bg-blue-500 transition-all duration-150"
              style={{ width: `${String(upload.progress)}%` }}
            />
          </div>
        )}

        {upload.status === UploadStatus.FAILED && upload.error !== null && (
          <p className="text-xs text-red-500 mt-0.5">{upload.error}</p>
        )}

        {upload.status === UploadStatus.CONFLICT && (
          <p className="text-xs text-amber-600 mt-0.5">Conflict - awaiting resolution</p>
        )}
      </div>

      <div className="flex-shrink-0">
        {upload.status === UploadStatus.QUEUED && (
          <span className="text-xs text-gray-400">Queued</span>
        )}

        {upload.status === UploadStatus.UPLOADING && (
          <span className="text-xs text-blue-500 font-medium">
            {upload.progress}%
          </span>
        )}

        {upload.status === UploadStatus.DONE && (
          <CheckCircle className="h-4 w-4 text-green-500" />
        )}

        {upload.status === UploadStatus.FAILED && (
          <button
            type="button"
            onClick={() => onRetry(upload.id)}
            className="p-1 text-gray-400 hover:text-blue-500"
            title="Retry"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        )}

        {upload.status === UploadStatus.CONFLICT && (
          <span className="text-xs text-amber-500 font-medium">!</span>
        )}
      </div>
    </div>
  );
}

/**
 * Floating upload panel positioned bottom-right (Google Drive-style).
 * Shows per-file progress, status indicators, and collapse toggle.
 * Renders nothing when no uploads exist.
 */
function UploadPanel({
  uploads,
  collapsed,
  onToggleCollapse,
  onClearCompleted,
  onRetry,
}: UploadPanelProps) {
  if (uploads.length === 0) {
    return null;
  }

  const completedCount = uploads.filter(
    (u) => u.status === UploadStatus.DONE,
  ).length;

  const hasCompleted = completedCount > 0;

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-lg bg-white shadow-lg border border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-t-lg">
        <span className="text-sm font-medium text-gray-700">
          Uploads ({uploads.length})
        </span>
        <div className="flex items-center gap-1">
          {hasCompleted && (
            <button
              type="button"
              onClick={onClearCompleted}
              className="p-1 text-gray-400 hover:text-gray-600"
              title="Clear completed"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onToggleCollapse}
            className="p-1 text-gray-400 hover:text-gray-600"
            title={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {/* Upload list (hidden when collapsed) */}
      {!collapsed && (
        <div className="max-h-64 overflow-y-auto">
          {uploads.map((upload) => (
            <UploadItem key={upload.id} upload={upload} onRetry={onRetry} />
          ))}
        </div>
      )}
    </div>
  );
}

export default UploadPanel;
