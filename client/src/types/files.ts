/** File type discriminator matching backend FileType enum values. */
export const FileType = {
  FILE: "file",
  DIRECTORY: "directory",
} as const;

export type FileType = (typeof FileType)[keyof typeof FileType];

export interface FileEntry {
  name: string;
  size: number;
  size_display: string;
  type: FileType;
  modified: string;
}

export interface DirectoryListing {
  path: string;
  entries: FileEntry[];
}
