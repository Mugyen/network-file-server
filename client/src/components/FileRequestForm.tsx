import { useRef, useState } from "react";

interface FileRequestFormProps {
  onSubmit: (description: string) => void;
  onCancel: () => void;
}

/** Inline form for creating a new file request with description. */
function FileRequestForm({ onSubmit, onCancel }: FileRequestFormProps) {
  const [description, setDescription] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(): void {
    const trimmed = description.trim();
    if (trimmed.length === 0) return;
    onSubmit(trimmed);
    setDescription("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if (e.key === "Enter") {
      handleSubmit();
    } else if (e.key === "Escape") {
      onCancel();
    }
  }

  return (
    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mb-3">
      <label className="block text-sm font-medium text-blue-800 dark:text-blue-300 mb-1.5">
        What file do you need?
      </label>
      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g. Meeting notes from today"
          autoFocus
          className="flex-1 rounded-md border border-blue-300 dark:border-blue-700 bg-white dark:bg-gray-800 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={description.trim().length === 0}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Request
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default FileRequestForm;
