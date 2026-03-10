import { Plus, X } from "lucide-react";
import type { Snippet } from "../types/clipboard.ts";
import SnippetCard from "./SnippetCard.tsx";

interface ScratchpadPanelProps {
  isOpen: boolean;
  snippets: Snippet[];
  isLoading: boolean;
  onClose: () => void;
  onAddSnippet: () => void;
  onUpdateContent: (id: string, content: string) => void;
  onUpdateTitle: (id: string, title: string) => void;
  onDeleteSnippet: (id: string) => void;
  readOnly: boolean;
}

function ScratchpadPanel({
  isOpen,
  snippets,
  isLoading,
  onClose,
  onAddSnippet,
  onUpdateContent,
  onUpdateTitle,
  onDeleteSnippet,
  readOnly,
}: ScratchpadPanelProps) {
  return (
    <>
      {/* Backdrop overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full sm:w-96 bg-gray-50 dark:bg-gray-900 shadow-xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
            Scratchpad
          </h2>
          <div className="flex items-center gap-2">
            {!readOnly && (
              <button
                type="button"
                onClick={onAddSnippet}
                className="p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
                aria-label="Add snippet"
              >
                <Plus className="w-5 h-5" />
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
              aria-label="Close scratchpad"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {isLoading && (
            <p className="text-center text-gray-500 dark:text-gray-400 py-8">
              Loading...
            </p>
          )}

          {!isLoading && snippets.length === 0 && (
            <p className="text-center text-gray-500 dark:text-gray-400 py-8">
              {readOnly ? "No snippets." : "No snippets yet. Click + to create one."}
            </p>
          )}

          {!isLoading &&
            snippets.map((snippet) => (
              <SnippetCard
                key={snippet.id}
                snippet={snippet}
                onUpdateContent={onUpdateContent}
                onUpdateTitle={onUpdateTitle}
                onDelete={onDeleteSnippet}
                readOnly={readOnly}
              />
            ))}
        </div>
      </div>
    </>
  );
}

export default ScratchpadPanel;
