import { Download, Trash2, X } from "lucide-react";

interface BatchToolbarProps {
  selectedCount: number;
  onDownloadZip: () => void;
  onDelete: () => void;
  onClearSelection: () => void;
  readOnly?: boolean;
}

/**
 * Contextual toolbar replacing the normal Toolbar when files are selected.
 * Shows selection count with Download ZIP, Delete, and Clear buttons (Gmail-style).
 * In read-only mode, the Delete button is hidden.
 */
function BatchToolbar({
  selectedCount,
  onDownloadZip,
  onDelete,
  onClearSelection,
  readOnly,
}: BatchToolbarProps) {
  return (
    <div className="flex flex-row items-center gap-3 bg-blue-50 dark:bg-blue-900/30 py-2 px-4 rounded-md">
      <span className="text-sm font-medium text-blue-800 dark:text-blue-300">
        {selectedCount} selected
      </span>

      <button
        type="button"
        onClick={onDownloadZip}
        className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
      >
        <Download className="h-4 w-4" />
        Download ZIP
      </button>

      {!readOnly && (
        <button
          type="button"
          onClick={onDelete}
          className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 transition-colors"
        >
          <Trash2 className="h-4 w-4" />
          Delete
        </button>
      )}

      <button
        type="button"
        onClick={onClearSelection}
        className="ml-auto p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
        title="Clear selection"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default BatchToolbar;
