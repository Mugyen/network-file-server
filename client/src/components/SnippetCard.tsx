import { useState, useRef } from "react";
import { ChevronDown, ChevronRight, Copy, Check, X } from "lucide-react";
import type { Snippet } from "../types/clipboard.ts";
import { copyToClipboard } from "../utils/copyToClipboard.ts";

interface SnippetCardProps {
  snippet: Snippet;
  onUpdateContent: (id: string, content: string) => void;
  onUpdateTitle: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  readOnly: boolean;
}

function SnippetCard({
  snippet,
  onUpdateContent,
  onUpdateTitle,
  onDelete,
  readOnly,
}: SnippetCardProps) {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const titleRef = useRef<HTMLInputElement>(null);

  function handleCopy(): void {
    void copyToClipboard(snippet.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function handleTitleBlur(): void {
    const input = titleRef.current;
    if (input === null) return;
    const value = input.value.trim();
    if (value !== "" && value !== snippet.title) {
      onUpdateTitle(snippet.id, value);
    }
  }

  function handleTitleKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if (e.key === "Enter") {
      e.currentTarget.blur();
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-1 px-2 py-1.5">
        <button
          type="button"
          onClick={() => setIsCollapsed((prev) => !prev)}
          className="p-0.5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
          aria-label={isCollapsed ? "Expand snippet" : "Collapse snippet"}
        >
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </button>

        <input
          ref={titleRef}
          type="text"
          defaultValue={snippet.title}
          onBlur={handleTitleBlur}
          onKeyDown={handleTitleKeyDown}
          readOnly={readOnly}
          className="flex-1 min-w-0 text-sm font-medium bg-transparent border-none outline-none text-gray-800 dark:text-gray-100 placeholder-gray-400"
          aria-label="Snippet title"
        />

        <button
          type="button"
          onClick={handleCopy}
          className="p-0.5 text-gray-400 hover:text-blue-500 dark:hover:text-blue-400"
          aria-label="Copy to clipboard"
        >
          {copied ? (
            <Check className="w-4 h-4 text-green-500" />
          ) : (
            <Copy className="w-4 h-4" />
          )}
        </button>

        {!readOnly && (
          <button
            type="button"
            onClick={() => onDelete(snippet.id)}
            className="p-0.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400"
            aria-label="Delete snippet"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Body */}
      {!isCollapsed && (
        <div className="px-2 pb-2">
          <textarea
            value={snippet.content}
            onChange={(e) => onUpdateContent(snippet.id, e.target.value)}
            readOnly={readOnly}
            placeholder={readOnly ? "" : "Type something..."}
            className="w-full min-h-[100px] resize-y text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-600 rounded p-2 text-gray-800 dark:text-gray-100 placeholder-gray-400 outline-none focus:border-blue-400 dark:focus:border-blue-500"
          />
        </div>
      )}
    </div>
  );
}

export default SnippetCard;
