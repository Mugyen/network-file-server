import type { DirectoryListing, FileEntry } from "../types/files.ts";
import { apiFetch, apiPost, apiPatch, apiDelete } from "./client.ts";
import { getApiBase } from "../utils/remoteMount.ts";

/** Response shape from the /files/search endpoint. */
export interface SearchResult {
  query: string;
  path: string;
  entries: FileEntry[];
}

export function fetchFiles(path: string): Promise<DirectoryListing> {
  return apiFetch<DirectoryListing>(
    `/files?path=${encodeURIComponent(path)}`
  );
}

/**
 * Trigger a direct browser download for a single file.
 * Creates a temporary anchor element with the download attribute.
 */
export function downloadFile(path: string): void {
  const a = document.createElement("a");
  a.href = `${getApiBase()}/files/download?path=${encodeURIComponent(path)}`;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Download multiple files as a ZIP archive.
 * POSTs selected paths to the server, receives a blob, triggers browser save.
 */
export async function downloadAsZip(paths: string[]): Promise<void> {
  const response = await fetch(`${getApiBase()}/files/download-zip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`ZIP download failed: ${text}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "files.zip";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Delete one or more files/folders by path.
 */
export function deleteFiles(paths: string[]): Promise<{ deleted: string[] }> {
  return apiDelete<{ deleted: string[] }>("/files", { paths });
}

/**
 * Rename a file or folder.
 */
export function renameFile(path: string, newName: string): Promise<{ path: string }> {
  return apiPatch<{ path: string }>("/files/rename", {
    path,
    new_name: newName,
  });
}

/**
 * Create a new folder inside parentPath.
 */
export function createFolder(parentPath: string, name: string): Promise<{ path: string }> {
  return apiPost<{ path: string }>("/folders", {
    parent_path: parentPath,
    name,
  });
}

/**
 * Search files recursively under a given path.
 * Returns entries with paths relative to the search root.
 */
export function searchFiles(query: string, path: string): Promise<SearchResult> {
  return apiFetch<SearchResult>(
    `/files/search?q=${encodeURIComponent(query)}&path=${encodeURIComponent(path)}`
  );
}
