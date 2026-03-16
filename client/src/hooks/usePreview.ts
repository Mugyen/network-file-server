import { useState, useEffect, useCallback } from "react";
import type { FileEntry } from "../types/files.ts";
import { FileCategory, getFileCategory } from "../types/fileCategories.ts";
import { getApiBase } from "../utils/remoteMount.ts";

/** Maximum file size in bytes for text content preview (500KB). */
const MAX_TEXT_PREVIEW_BYTES = 512_000;

/** Categories that require fetching text content for preview. */
const TEXT_CONTENT_CATEGORIES: ReadonlySet<FileCategory> = new Set([
  FileCategory.CODE,
  FileCategory.TEXT,
  FileCategory.MARKDOWN,
]);

function buildFullPath(currentPath: string, fileName: string): string {
  if (currentPath === "") {
    return fileName;
  }
  return currentPath + "/" + fileName;
}

interface PreviewState {
  previewFile: FileEntry | null;
  openPreview: (file: FileEntry) => void;
  closePreview: () => void;
  textContent: string | null;
  isLoadingContent: boolean;
  contentError: string | null;
}

/**
 * Manages preview modal state including which file is being previewed
 * and text content fetching for code/text/markdown files.
 *
 * Automatically fetches text content when a text-based file is previewed.
 * Enforces a 500KB size limit on text previews.
 * Closes preview when currentPath changes (navigation).
 */
export function usePreview(currentPath: string): PreviewState {
  const [previewFile, setPreviewFile] = useState<FileEntry | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [isLoadingContent, setIsLoadingContent] = useState<boolean>(false);
  const [contentError, setContentError] = useState<string | null>(null);

  const closePreview = useCallback((): void => {
    setPreviewFile(null);
    setTextContent(null);
    setContentError(null);
    setIsLoadingContent(false);
  }, []);

  // Close preview when navigating to a different directory
  useEffect(() => {
    closePreview();
  }, [currentPath, closePreview]);

  const openPreview = useCallback(
    (file: FileEntry): void => {
      setPreviewFile(file);
      setTextContent(null);
      setContentError(null);

      const category = getFileCategory(file.name);
      if (!TEXT_CONTENT_CATEGORIES.has(category)) {
        setIsLoadingContent(false);
        return;
      }

      // Check file size before fetching
      if (file.size > MAX_TEXT_PREVIEW_BYTES) {
        setContentError("File too large to preview");
        setIsLoadingContent(false);
        return;
      }

      const fullPath = buildFullPath(currentPath, file.name);
      const url = `${getApiBase()}/files/preview?path=${encodeURIComponent(fullPath)}`;

      setIsLoadingContent(true);

      fetch(url)
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Failed to fetch preview: ${String(response.status)}`);
          }

          const contentLength = response.headers.get("Content-Length");
          if (contentLength !== null && parseInt(contentLength, 10) > MAX_TEXT_PREVIEW_BYTES) {
            throw new Error("File too large to preview");
          }

          return response.text();
        })
        .then((text) => {
          setTextContent(text);
          setIsLoadingContent(false);
        })
        .catch((err: unknown) => {
          const message = err instanceof Error ? err.message : "Failed to load file content";
          setContentError(message);
          setIsLoadingContent(false);
        });
    },
    [currentPath],
  );

  return {
    previewFile,
    openPreview,
    closePreview,
    textContent,
    isLoadingContent,
    contentError,
  };
}
