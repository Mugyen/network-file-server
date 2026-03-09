import type { FileEntry } from "../../types/files.ts";
import { Download, FileText } from "lucide-react";

interface FileInfoPreviewProps {
  file: FileEntry;
  downloadUrl: string;
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

/**
 * Fallback preview for non-previewable files.
 * Shows file metadata (name, size, type, date) and a download button.
 */
function FileInfoPreview({ file, downloadUrl }: FileInfoPreviewProps) {
  const dotIndex = file.name.lastIndexOf(".");
  const extension =
    dotIndex !== -1 && dotIndex < file.name.length - 1
      ? file.name.slice(dotIndex + 1).toUpperCase()
      : "Unknown";

  return (
    <div className="flex flex-col items-center gap-6 py-8 px-4">
      <FileText className="h-20 w-20 text-gray-400 dark:text-gray-500" />

      <div className="text-center">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 break-all">
          {file.name}
        </h3>
      </div>

      <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
        <span className="text-gray-500 dark:text-gray-400">Size</span>
        <span className="text-gray-800 dark:text-gray-200">{file.size_display}</span>

        <span className="text-gray-500 dark:text-gray-400">Type</span>
        <span className="text-gray-800 dark:text-gray-200">{extension} file</span>

        <span className="text-gray-500 dark:text-gray-400">Modified</span>
        <span className="text-gray-800 dark:text-gray-200">{formatDate(file.modified)}</span>
      </div>

      <a
        href={downloadUrl}
        download
        className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
      >
        <Download className="h-4 w-4" />
        Download
      </a>
    </div>
  );
}

export default FileInfoPreview;
