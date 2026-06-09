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

/** Allowed upload-TTL values in seconds (0 = never expires).
 * Mirrors the ShareTTL const pattern in api/shares.ts. */
export const UploadTTL = {
  ONE_HOUR: 3600,
  SIX_HOURS: 21600,
  ONE_DAY: 86400,
  SEVEN_DAYS: 604800,
  NEVER: 0,
} as const;

export type UploadTTL = (typeof UploadTTL)[keyof typeof UploadTTL];

/** Human-readable labels for each upload TTL value. */
export const UPLOAD_TTL_LABELS: Record<UploadTTL, string> = {
  [UploadTTL.ONE_HOUR]: "1 hour",
  [UploadTTL.SIX_HOURS]: "6 hours",
  [UploadTTL.ONE_DAY]: "1 day",
  [UploadTTL.SEVEN_DAYS]: "7 days",
  [UploadTTL.NEVER]: "Never",
};

/** All upload TTL options in display order. */
export const UPLOAD_TTL_OPTIONS: UploadTTL[] = [
  UploadTTL.ONE_HOUR,
  UploadTTL.SIX_HOURS,
  UploadTTL.ONE_DAY,
  UploadTTL.SEVEN_DAYS,
  UploadTTL.NEVER,
];

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
