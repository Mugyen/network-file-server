import type { DirectoryListing } from "../types/files.ts";
import { apiFetch } from "./client.ts";

export function fetchFiles(path: string): Promise<DirectoryListing> {
  return apiFetch<DirectoryListing>(
    `/files?path=${encodeURIComponent(path)}`
  );
}
