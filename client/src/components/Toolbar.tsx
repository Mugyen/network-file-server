import { Upload, FolderPlus, FileQuestion } from "lucide-react";
import { useRef } from "react";

interface ToolbarProps {
  onUploadClick: (files: FileList) => void;
  onNewFolder: () => void;
  onRequestFile: () => void;
  currentPath: string;
  fileTtl: number;
  onFileTtlChange: (ttl: number) => void;
}

/**
 * Toolbar with Upload button (opens hidden file input) and
 * New Folder button (triggers create folder dialog in parent).
 */
function Toolbar({ onUploadClick, onNewFolder, onRequestFile, currentPath: _currentPath, fileTtl, onFileTtlChange }: ToolbarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleUploadButtonClick(): void {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const files = e.target.files;
    if (files !== null && files.length > 0) {
      onUploadClick(files);
    }
    // Reset so selecting the same file again triggers onChange
    e.target.value = "";
  }

  return (
    <div className="flex flex-row items-center gap-2 py-2">
      <button
        type="button"
        onClick={handleUploadButtonClick}
        className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
      >
        <Upload className="h-4 w-4" />
        Upload
      </button>

      <select
        value={String(fileTtl)}
        onChange={(e) => onFileTtlChange(Number(e.target.value))}
        className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-700 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-300"
        title="File expiry"
      >
        <option value="3600">1 hour</option>
        <option value="21600">6 hours</option>
        <option value="86400">1 day</option>
        <option value="604800">7 days</option>
        <option value="0">Never</option>
      </select>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={handleFileChange}
        className="hidden"
      />

      <button
        type="button"
        onClick={onNewFolder}
        className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
      >
        <FolderPlus className="h-4 w-4" />
        New Folder
      </button>

      <button
        type="button"
        onClick={onRequestFile}
        className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
      >
        <FileQuestion className="h-4 w-4" />
        Request File
      </button>
    </div>
  );
}

export default Toolbar;
