/** Upload status discriminator. */
export const UploadStatus = {
  QUEUED: "queued",
  UPLOADING: "uploading",
  DONE: "done",
  FAILED: "failed",
  CONFLICT: "conflict",
} as const;

export type UploadStatus = (typeof UploadStatus)[keyof typeof UploadStatus];

/** Conflict resolution action chosen by the user. */
export const ConflictAction = {
  OVERWRITE: "overwrite",
  RENAME: "rename",
  SKIP: "skip",
} as const;

export type ConflictAction = (typeof ConflictAction)[keyof typeof ConflictAction];

/** State for a single file in the upload queue. */
export interface UploadFileState {
  id: string;
  file: File;
  status: UploadStatus;
  progress: number;
  error: string | null;
  conflictAction: ConflictAction | null;
}

/** Server response for a single uploaded file. */
export interface UploadResult {
  name: string;
  size: number;
  size_display: string;
  skipped: boolean;
}
