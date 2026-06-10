/**
 * File-listing types. Interfaces are derived from the server's OpenAPI schema
 * (single source of truth); the FileType runtime const is kept here because
 * components compare against its values (FileType.DIRECTORY etc.).
 */
import type { Schemas } from "./api.ts";

/** File type discriminator matching backend FileType enum values. */
export const FileType = {
  FILE: "file",
  DIRECTORY: "directory",
} as const;

export type FileType = (typeof FileType)[keyof typeof FileType];

export type FileEntry = Schemas["FileEntry"];
export type DirectoryListing = Schemas["DirectoryListing"];
