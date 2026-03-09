import { useRef, useState } from "react";
import { FileQuestion, CheckCircle, Upload, X, Download } from "lucide-react";
import type { FileRequest } from "../types/fileRequests.ts";
import { RequestStatus } from "../types/fileRequests.ts";

interface FileRequestBannerProps {
  request: FileRequest;
  isOwner: boolean;
  fulfillProgress: number | undefined;
  onFulfill: (requestId: string, file: File) => void;
  onDismiss: (requestId: string) => void;
  onDownload: (path: string) => void;
}

/** Banner card displayed above file list for each active file request. */
function FileRequestBanner({
  request,
  isOwner,
  fulfillProgress,
  onFulfill,
  onDismiss,
  onDownload,
}: FileRequestBannerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  function handleUploadClick(): void {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const files = e.target.files;
    if (files !== null && files.length > 0) {
      onFulfill(request.id, files[0]);
    }
    e.target.value = "";
  }

  function handleDragOver(e: React.DragEvent): void {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }

  function handleDragLeave(e: React.DragEvent): void {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }

  function handleDrop(e: React.DragEvent): void {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file !== undefined) {
      onFulfill(request.id, file);
    }
  }

  if (request.status === RequestStatus.PENDING) {
    return (
      <div
        className={`bg-amber-50 dark:bg-amber-900/20 border rounded-lg p-3 mb-2 transition-colors ${
          isDragOver
            ? "border-amber-500 dark:border-amber-400 bg-amber-100 dark:bg-amber-900/40"
            : "border-amber-300 dark:border-amber-700"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex items-center gap-2">
          <FileQuestion className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-amber-900 dark:text-amber-200">
              <span className="font-medium">{request.requester_device_name}</span>
              {" is requesting: "}
              <span className="font-medium">{request.description}</span>
            </p>
          </div>
          {fulfillProgress !== undefined ? (
            <div className="w-24 h-2 bg-amber-200 dark:bg-amber-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-500 dark:bg-amber-400 transition-all"
                style={{ width: `${String(fulfillProgress)}%` }}
              />
            </div>
          ) : (
            <button
              type="button"
              onClick={handleUploadClick}
              className="inline-flex items-center gap-1 rounded-md bg-amber-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-700 transition-colors shrink-0"
            >
              <Upload className="h-3.5 w-3.5" />
              Upload
            </button>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileChange}
          className="hidden"
        />
      </div>
    );
  }

  // Fulfilled state
  return (
    <div className="bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded-lg p-3 mb-2">
      <div className="flex items-center gap-2">
        <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-green-900 dark:text-green-200">
            <span className="font-medium">Fulfilled by {request.fulfilled_by_device_name}</span>
            {": "}
            <button
              type="button"
              onClick={() => {
                if (request.fulfilled_file_path !== null) {
                  onDownload(request.fulfilled_file_path);
                }
              }}
              className="font-medium underline hover:text-green-700 dark:hover:text-green-300"
            >
              {request.fulfilled_file_name}
            </button>
          </p>
        </div>
        {request.fulfilled_file_path !== null && (
          <button
            type="button"
            onClick={() => onDownload(request.fulfilled_file_path!)}
            className="inline-flex items-center gap-1 rounded-md border border-green-300 dark:border-green-700 bg-white dark:bg-gray-800 px-2.5 py-1 text-xs font-medium text-green-700 dark:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/40 transition-colors shrink-0"
          >
            <Download className="h-3.5 w-3.5" />
          </button>
        )}
        {isOwner && (
          <button
            type="button"
            onClick={() => onDismiss(request.id)}
            className="inline-flex items-center rounded-md p-1 text-green-600 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/40 transition-colors shrink-0"
            title="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

export default FileRequestBanner;
