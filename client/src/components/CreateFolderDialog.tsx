import { useEffect, useRef, useState } from "react";

interface CreateFolderDialogProps {
  onCreateFolder: (name: string) => void;
  onCancel: () => void;
}

/**
 * Modal dialog with text input for creating a new folder.
 * Auto-focuses the input field on mount. Rejects empty names with inline error.
 */
function CreateFolderDialog({
  onCreateFolder,
  onCancel,
}: CreateFolderDialogProps) {
  const [name, setName] = useState<string>("");
  const [error, setError] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleSubmit(e: React.FormEvent): void {
    e.preventDefault();
    const trimmed = name.trim();
    if (trimmed === "") {
      setError("Folder name cannot be empty");
      return;
    }
    onCreateFolder(trimmed);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>): void {
    setName(e.target.value);
    if (error !== "") {
      setError("");
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg bg-white dark:bg-gray-800 p-6 shadow-xl">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-4">
          New Folder
        </h3>

        <form onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="text"
            value={name}
            onChange={handleChange}
            placeholder="Folder name"
            className={`w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400 ${
              error !== ""
                ? "border-red-300 focus:ring-red-500"
                : "border-gray-300 focus:ring-blue-500 dark:border-gray-600 dark:focus:ring-blue-400"
            }`}
          />
          {error !== "" && (
            <p className="mt-1 text-xs text-red-500">{error}</p>
          )}

          <div className="mt-4 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CreateFolderDialog;
