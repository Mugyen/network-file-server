import { useEffect, useCallback } from "react";
import type { FileEntry } from "../types/files.ts";
import { FileCategory, getFileCategory } from "../types/fileCategories.ts";
import { API_ROUTES } from "../api/endpoints.ts";
import { getApiBase } from "../utils/remoteMount.ts";
import { X, ExternalLink, Download, Loader2 } from "lucide-react";
import ImagePreview from "./preview/ImagePreview.tsx";
import VideoPreview from "./preview/VideoPreview.tsx";
import AudioPreview from "./preview/AudioPreview.tsx";
import PdfPreview from "./preview/PdfPreview.tsx";
import CodePreview from "./preview/CodePreview.tsx";
import MarkdownPreview from "./preview/MarkdownPreview.tsx";
import FileInfoPreview from "./preview/FileInfoPreview.tsx";

interface PreviewModalProps {
  file: FileEntry;
  files: FileEntry[];
  currentPath: string;
  textContent: string | null;
  isLoadingContent: boolean;
  contentError: string | null;
  isDark: boolean;
  onClose: () => void;
  onNavigateFile: (file: FileEntry) => void;
}

function buildFullPath(currentPath: string, fileName: string): string {
  if (currentPath === "") {
    return fileName;
  }
  return currentPath + "/" + fileName;
}

function getFileExtension(fileName: string): string {
  const dotIndex = fileName.lastIndexOf(".");
  if (dotIndex === -1 || dotIndex === fileName.length - 1) {
    return "";
  }
  return fileName.slice(dotIndex + 1).toLowerCase();
}

/**
 * Modal shell for file preview with backdrop, header controls, and content switching.
 *
 * Renders the correct preview sub-component based on file category.
 * Header provides close, open-in-new-tab, and download buttons.
 * Escape key and backdrop click close the modal.
 */
function PreviewModal({
  file,
  files,
  currentPath,
  textContent,
  isLoadingContent,
  contentError,
  isDark,
  onClose,
  onNavigateFile,
}: PreviewModalProps) {
  const fullPath = buildFullPath(currentPath, file.name);
  const apiBase = getApiBase();
  const previewUrl = `${apiBase}${API_ROUTES.filesPreview}?path=${encodeURIComponent(fullPath)}`;
  const downloadUrl = `${apiBase}${API_ROUTES.filesDownload}?path=${encodeURIComponent(fullPath)}`;
  const category = getFileCategory(file.name);

  // Close on Escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        onClose();
      }
    },
    [onClose],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Close on backdrop click
  function handleBackdropClick(e: React.MouseEvent<HTMLDivElement>): void {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  function handleOpenNewTab(): void {
    window.open(previewUrl, "_blank");
  }

  // --- Content rendering ---

  function renderLoadingSpinner(): React.ReactNode {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  function renderError(message: string): React.ReactNode {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-red-500 dark:text-red-400">{message}</p>
      </div>
    );
  }

  function renderTextContent(
    renderFn: (content: string) => React.ReactNode,
  ): React.ReactNode {
    if (isLoadingContent) {
      return renderLoadingSpinner();
    }
    if (contentError !== null) {
      return renderError(contentError);
    }
    if (textContent === null) {
      return renderLoadingSpinner();
    }
    return renderFn(textContent);
  }

  function renderContent(): React.ReactNode {
    switch (category) {
      case FileCategory.IMAGES: {
        const imageFiles = files.filter(
          (f) => getFileCategory(f.name) === FileCategory.IMAGES,
        );
        const currentIndex = imageFiles.findIndex((f) => f.name === file.name);
        const safeIndex = currentIndex === -1 ? 0 : currentIndex;

        function handleImageNavigate(index: number): void {
          const target = imageFiles[index];
          if (target !== undefined) {
            onNavigateFile(target);
          }
        }

        const imageFullPath = buildFullPath(currentPath, file.name);
        const imageDownloadUrl = `${apiBase}${API_ROUTES.filesDownload}?path=${encodeURIComponent(imageFullPath)}`;

        return (
          <ImagePreview
            url={previewUrl}
            file={file}
            imageFiles={imageFiles}
            currentIndex={safeIndex}
            onNavigate={handleImageNavigate}
            downloadUrl={imageDownloadUrl}
          />
        );
      }

      case FileCategory.VIDEO:
        return <VideoPreview url={previewUrl} file={file} />;

      case FileCategory.AUDIO:
        return <AudioPreview url={previewUrl} file={file} />;

      case FileCategory.DOCUMENTS: {
        const ext = getFileExtension(file.name);
        if (ext === "pdf") {
          return <PdfPreview url={previewUrl} file={file} />;
        }
        return <FileInfoPreview file={file} downloadUrl={downloadUrl} />;
      }

      case FileCategory.CODE:
        return renderTextContent((content) => (
          <CodePreview content={content} fileName={file.name} isDark={isDark} />
        ));

      case FileCategory.MARKDOWN:
        return renderTextContent((content) => (
          <MarkdownPreview content={content} />
        ));

      case FileCategory.TEXT:
        return renderTextContent((content) => (
          <CodePreview content={content} fileName="plain.txt" isDark={isDark} />
        ));

      default:
        return <FileInfoPreview file={file} downloadUrl={downloadUrl} />;
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
    >
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-5xl w-full mx-4 max-h-[90vh] flex flex-col">
        {/* Header bar */}
        <div className="flex items-center justify-between border-b dark:border-gray-700 px-4 py-3">
          <h2
            className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate flex-1 mr-4"
            title={file.name}
          >
            {file.name}
          </h2>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleOpenNewTab}
              className="p-1.5 text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400 transition-colors"
              title="Open in new tab"
            >
              <ExternalLink className="h-4 w-4" />
            </button>

            <a
              href={downloadUrl}
              download
              className="p-1.5 text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400 transition-colors"
              title="Download"
            >
              <Download className="h-4 w-4" />
            </a>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              title="Close (Esc)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-auto p-4">{renderContent()}</div>
      </div>
    </div>
  );
}

export default PreviewModal;
