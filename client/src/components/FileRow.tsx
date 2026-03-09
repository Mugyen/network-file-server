import { useState, useRef, useEffect } from "react";
import { FileType } from "../types/files.ts";
import type { FileEntry } from "../types/files.ts";
import FileIcon from "./FileIcon.tsx";
import { Download, Pencil, Trash2 } from "lucide-react";

interface FileRowProps {
  file: FileEntry;
  currentPath: string;
  isSelected: boolean;
  onSelect: (name: string) => void;
  onNavigate: (path: string) => void;
  onRename: (path: string, newName: string) => Promise<void>;
  onDelete: (path: string) => void;
  onDownload: (path: string) => void;
  onPreview: (file: FileEntry) => void;
}

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function buildChildPath(currentPath: string, childName: string): string {
  if (currentPath === "") {
    return childName;
  }
  return currentPath + "/" + childName;
}

function FileRow({
  file,
  currentPath,
  isSelected,
  onSelect,
  onNavigate,
  onRename,
  onDelete,
  onDownload,
  onPreview,
}: FileRowProps) {
  const isDirectory = file.type === FileType.DIRECTORY;
  const fullPath = buildChildPath(currentPath, file.name);

  const [isRenaming, setIsRenaming] = useState<boolean>(false);
  const [renameValue, setRenameValue] = useState<string>(file.name);
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isRenaming) {
      renameInputRef.current?.focus();
      renameInputRef.current?.select();
    }
  }, [isRenaming]);

  function handleDoubleClick(): void {
    if (isDirectory) {
      onNavigate(fullPath);
    }
  }

  function handleNameClick(): void {
    if (isDirectory) {
      onNavigate(fullPath);
    } else {
      onPreview(file);
    }
  }

  function handleCheckboxChange(): void {
    onSelect(file.name);
  }

  function handleRenameStart(): void {
    setRenameValue(file.name);
    setIsRenaming(true);
  }

  async function handleRenameConfirm(): Promise<void> {
    const trimmed = renameValue.trim();
    if (trimmed === "" || trimmed === file.name) {
      setIsRenaming(false);
      return;
    }
    await onRename(fullPath, trimmed);
    setIsRenaming(false);
  }

  function handleRenameKeyDown(e: React.KeyboardEvent): void {
    if (e.key === "Enter") {
      void handleRenameConfirm();
    } else if (e.key === "Escape") {
      setIsRenaming(false);
    }
  }

  function handleDeleteClick(): void {
    onDelete(fullPath);
  }

  function handleDownloadClick(): void {
    onDownload(fullPath);
  }

  return (
    <tr
      className={`border-b dark:border-gray-700 group ${isSelected ? "bg-blue-50 dark:bg-blue-900/20" : "hover:bg-gray-50 dark:hover:bg-gray-800"} ${isDirectory ? "cursor-pointer" : ""}`}
      onDoubleClick={handleDoubleClick}
    >
      {/* Checkbox column */}
      <td className="py-2 px-2 w-10">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={handleCheckboxChange}
          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
      </td>

      {/* Name column */}
      <td className="py-2 px-3 dark:text-gray-200">
        <span className="inline-flex items-center gap-2">
          <FileIcon fileName={file.name} isDirectory={isDirectory} />
          {isRenaming ? (
            <input
              ref={renameInputRef}
              type="text"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={() => void handleRenameConfirm()}
              onKeyDown={handleRenameKeyDown}
              className="rounded border border-blue-300 px-1.5 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-gray-700 dark:border-blue-500 dark:text-gray-100"
            />
          ) : (
            <button
              type="button"
              onClick={handleNameClick}
              className={`text-left hover:text-blue-600 dark:hover:text-blue-400 ${isDirectory ? "font-bold" : ""}`}
            >
              {file.name}
            </button>
          )}
        </span>
      </td>

      {/* Size column */}
      <td className="py-2 px-3 text-gray-600 dark:text-gray-400 hidden md:table-cell">
        {file.size_display}
      </td>

      {/* Modified column */}
      <td className="py-2 px-3 text-gray-600 dark:text-gray-400 hidden md:table-cell">
        {formatDate(file.modified)}
      </td>

      {/* Actions column -- visible on row hover */}
      <td className="py-2 px-3 text-right">
        <div className="invisible group-hover:visible inline-flex items-center gap-1">
          {!isDirectory && (
            <button
              type="button"
              onClick={handleDownloadClick}
              className="p-1 text-gray-400 hover:text-blue-600 dark:text-gray-500 dark:hover:text-blue-400 transition-colors"
              title="Download"
            >
              <Download className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={handleRenameStart}
            className="p-1 text-gray-400 hover:text-blue-600 dark:text-gray-500 dark:hover:text-blue-400 transition-colors"
            title="Rename"
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={handleDeleteClick}
            className="p-1 text-gray-400 hover:text-red-600 dark:text-gray-500 dark:hover:text-red-400 transition-colors"
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </td>
    </tr>
  );
}

export default FileRow;
