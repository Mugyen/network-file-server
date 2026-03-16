import { ApiError } from "./client.ts";
import { apiPost, apiFetch } from "./client.ts";
import { getApiBase } from "../utils/remoteMount.ts";

/** Shape of a share link returned by the backend. */
export interface ShareLinkInfo {
  token: string;
  file_path: string;
  file_name: string;
  created_at: string;
  expires_at: string;
  ttl_seconds: number;
  share_url: string;
}

/** Allowed TTL values in seconds for share links. */
export const ShareTTL = {
  FIFTEEN_MINUTES: 900,
  ONE_HOUR: 3600,
  SIX_HOURS: 21600,
  TWENTY_FOUR_HOURS: 86400,
} as const;

export type ShareTTL = (typeof ShareTTL)[keyof typeof ShareTTL];

/** Human-readable labels for each TTL value. */
export const TTL_LABELS: Record<ShareTTL, string> = {
  [ShareTTL.FIFTEEN_MINUTES]: "15 minutes",
  [ShareTTL.ONE_HOUR]: "1 hour",
  [ShareTTL.SIX_HOURS]: "6 hours",
  [ShareTTL.TWENTY_FOUR_HOURS]: "24 hours",
};

/** All TTL options in display order. */
export const TTL_OPTIONS: ShareTTL[] = [
  ShareTTL.FIFTEEN_MINUTES,
  ShareTTL.ONE_HOUR,
  ShareTTL.SIX_HOURS,
  ShareTTL.TWENTY_FOUR_HOURS,
];

/**
 * Create a new share link for a file.
 * POST /api/shares with { file_path, ttl }.
 */
export function createShareLink(filePath: string, ttl: ShareTTL): Promise<ShareLinkInfo> {
  return apiPost<ShareLinkInfo>("/shares", { file_path: filePath, ttl });
}

/**
 * List all active (non-expired) share links.
 * GET /api/shares.
 */
export function listShareLinks(): Promise<ShareLinkInfo[]> {
  return apiFetch<ShareLinkInfo[]>("/shares");
}

/**
 * Revoke a share link by token.
 * DELETE /api/shares/{token}. Returns 204 with no body.
 *
 * Uses fetch directly because the generic apiDelete expects a JSON body
 * and parses a JSON response, but this endpoint uses neither.
 */
export async function revokeShareLink(token: string): Promise<void> {
  const response = await fetch(`${getApiBase()}/shares/${encodeURIComponent(token)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body);
  }
}
