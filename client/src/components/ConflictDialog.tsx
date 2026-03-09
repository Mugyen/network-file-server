import { ConflictAction } from "../types/upload.ts";

interface ConflictDialogProps {
  fileName: string;
  onResolve: (action: ConflictAction) => void;
}

/**
 * Modal dialog for per-file upload conflict resolution.
 * User must choose overwrite, rename, or skip -- no close/cancel.
 */
function ConflictDialog({ fileName, onResolve }: ConflictDialogProps) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white dark:bg-gray-800 p-6 shadow-xl">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-2">
          File Already Exists
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-300 mb-6">
          A file named <span className="font-medium">'{fileName}'</span> already
          exists. What would you like to do?
        </p>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => onResolve(ConflictAction.SKIP)}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-600 transition-colors"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={() => onResolve(ConflictAction.RENAME)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Rename
          </button>
          <button
            type="button"
            onClick={() => onResolve(ConflictAction.OVERWRITE)}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
          >
            Overwrite
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConflictDialog;
