/**
 * Remote mount detection and URL helpers.
 *
 * When the SPA is served through the relay at /m/{code}/, this module detects
 * that prefix and ensures all API and WebSocket URLs are correctly prefixed.
 * In LAN mode (no /m/ prefix), all helpers return standard /api/* paths.
 */

const MOUNT_CODE_PATTERN = /^(\/m\/[^/]+)/;

/**
 * Reads window.location.pathname and extracts the /m/{code} prefix if present.
 * Returns "" in LAN mode (no relay prefix).
 */
function detectMountPrefix(): string {
  const match = MOUNT_CODE_PATTERN.exec(window.location.pathname);
  if (match === null) {
    return "";
  }
  return match[1];
}

/** Module-level constant computed once at load time from the current URL. */
const MOUNT_PREFIX: string = detectMountPrefix();

/**
 * Returns the API base path, with or without the mount prefix.
 * - LAN mode:    "/api"
 * - Remote mode: "/m/{code}/api"
 */
export function getApiBase(): string {
  return MOUNT_PREFIX === "" ? "/api" : `${MOUNT_PREFIX}/api`;
}

/**
 * Returns true when the SPA is loaded through the relay (/m/{code}/ prefix).
 */
export function isRemoteMount(): boolean {
  return MOUNT_PREFIX !== "";
}

/**
 * Returns the raw mount prefix string (e.g. "/m/ABC12345" or "").
 */
export function getMountPrefix(): string {
  return MOUNT_PREFIX;
}

/**
 * Builds a fully-qualified WebSocket URL including protocol, host,
 * optional mount prefix, and query string.
 *
 * @param wsPath     - WebSocket path, e.g. "/ws"
 * @param queryString - Raw query string without "?", e.g. "device_name=foo"
 */
export function getWsUrl(wsPath: string, queryString: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  return `${protocol}//${host}${MOUNT_PREFIX}${wsPath}?${queryString}`;
}
