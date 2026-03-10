import { useEffect, useRef } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";
import type { FileEntry } from "../types/files.ts";
import type { SortField, SortDirection } from "../hooks/useSort.ts";
import { SortField as SF, SortDirection as SD } from "../hooks/useSort.ts";
import FileRow from "./FileRow.tsx";

interface FileListSelection {
  selectedNames: Set<string>;
  isAllSelected: boolean;
  isIndeterminate: boolean;
  toggleSelect: (name: string) => void;
  toggleSelectAll: () => void;
}

interface FileListProps {
  files: FileEntry[];
  currentPath: string;
  onNavigate: (path: string) => void;
  selection: FileListSelection;
  onRename: (path: string, newName: string) => Promise<void>;
  onDelete: (path: string) => void;
  onDownload: (path: string) => void;
  onPreview: (file: FileEntry) => void;
  sortField: SortField;
  sortDirection: SortDirection;
  onSort: (field: SortField) => void;
  readOnly?: boolean;
}

/** Renders the sort arrow icon for a column header. */
function SortArrow({ field, activeField, direction }: { field: SortField; activeField: SortField; direction: SortDirection }) {
  if (field !== activeField) {
    return null;
  }
  if (direction === SD.ASC) {
    return <ChevronUp className="h-3.5 w-3.5 inline-block ml-0.5" />;
  }
  return <ChevronDown className="h-3.5 w-3.5 inline-block ml-0.5" />;
}

function FileList({
  files,
  currentPath,
  onNavigate,
  selection,
  onRename,
  onDelete,
  onDownload,
  onPreview,
  sortField,
  sortDirection,
  onSort,
  readOnly,
}: FileListProps) {
  const selectAllRef = useRef<HTMLInputElement>(null);

  // Sync indeterminate state on the Select All checkbox via DOM ref
  // (HTML attribute "indeterminate" cannot be set via JSX)
  useEffect(() => {
    if (selectAllRef.current !== null) {
      selectAllRef.current.indeterminate = selection.isIndeterminate;
    }
  }, [selection.isIndeterminate]);

  if (files.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 dark:text-gray-400 text-lg">This folder is empty</p>
        {!readOnly && (
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
            Drag files here or use the Upload button
          </p>
        )}
      </div>
    );
  }

  return (
    <div>
      {selection.isAllSelected && (
        <div className="bg-blue-50 dark:bg-blue-900/30 text-sm text-blue-700 dark:text-blue-300 py-1.5 px-4 rounded-t-md border border-blue-100 dark:border-blue-800">
          All {files.length} items on this page are selected
        </div>
      )}

      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-gray-300 dark:border-gray-700">
            <th className="py-2 px-2 w-10 dark:bg-gray-800">
              <input
                ref={selectAllRef}
                type="checkbox"
                checked={selection.isAllSelected}
                onChange={selection.toggleSelectAll}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
            </th>
            <th className="py-2 px-3 font-semibold dark:bg-gray-800 dark:text-gray-100">
              <button
                type="button"
                onClick={() => onSort(SF.NAME)}
                className="inline-flex items-center hover:text-blue-600 dark:hover:text-blue-400"
              >
                Name
                <SortArrow field={SF.NAME} activeField={sortField} direction={sortDirection} />
              </button>
            </th>
            <th className="py-2 px-3 font-semibold hidden md:table-cell dark:bg-gray-800 dark:text-gray-100">
              <button
                type="button"
                onClick={() => onSort(SF.SIZE)}
                className="inline-flex items-center hover:text-blue-600 dark:hover:text-blue-400"
              >
                Size
                <SortArrow field={SF.SIZE} activeField={sortField} direction={sortDirection} />
              </button>
            </th>
            <th className="py-2 px-3 font-semibold hidden md:table-cell dark:bg-gray-800 dark:text-gray-100">
              <button
                type="button"
                onClick={() => onSort(SF.MODIFIED)}
                className="inline-flex items-center hover:text-blue-600 dark:hover:text-blue-400"
              >
                Modified
                <SortArrow field={SF.MODIFIED} activeField={sortField} direction={sortDirection} />
              </button>
            </th>
            <th className="py-2 px-3 w-28 dark:bg-gray-800">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {files.map((file) => (
            <FileRow
              key={file.name}
              file={file}
              currentPath={currentPath}
              isSelected={selection.selectedNames.has(file.name)}
              onSelect={selection.toggleSelect}
              onNavigate={onNavigate}
              onRename={onRename}
              onDelete={onDelete}
              onDownload={onDownload}
              onPreview={onPreview}
              readOnly={readOnly}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default FileList;
