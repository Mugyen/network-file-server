/**
 * Hand-rolled runtime type guards for WebSocket payloads.
 *
 * Incoming WS messages are untrusted JSON. These guards replace blind
 * `as` casts at consumption sites so a malformed message is logged and
 * skipped instead of corrupting state or crashing a render.
 */
import { DeviceType, ToastType, WSMessageType } from "../types/websocket.ts";
import type {
  DeviceInfo,
  WSDeviceCountPayload,
  WSDeviceListPayload,
  WSToastPayload,
} from "../types/websocket.ts";
import { RequestStatus } from "../types/fileRequests.ts";
import type { FileRequest } from "../types/fileRequests.ts";
import type { Snippet } from "../types/clipboard.ts";

/** Payload for SNIPPET_CREATED / SNIPPET_UPDATED messages. */
export interface WSSnippetPayload {
  snippet: Snippet;
}

/** Payload for SNIPPET_DELETED messages. */
export interface WSSnippetDeletedPayload {
  snippet_id: string;
}

/** Payload for REQUEST_CREATED / REQUEST_FULFILLED messages. */
export interface WSFileRequestPayload {
  request: FileRequest;
}

/** Payload for REQUEST_DISMISSED messages. */
export interface WSRequestDismissedPayload {
  request_id: string;
}

/** Narrow an unknown value to a plain object with string keys. */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isOneOf<T extends string>(
  allowed: readonly T[],
  value: unknown,
): value is T {
  return isString(value) && (allowed as readonly string[]).includes(value);
}

const DEVICE_TYPES: readonly DeviceType[] = Object.values(DeviceType);
const TOAST_TYPES: readonly ToastType[] = Object.values(ToastType);
const REQUEST_STATUSES: readonly RequestStatus[] = Object.values(RequestStatus);

export function isDeviceInfo(value: unknown): value is DeviceInfo {
  return (
    isRecord(value) &&
    isString(value.device_id) &&
    isString(value.device_name) &&
    isString(value.ip_address) &&
    isOneOf(DEVICE_TYPES, value.device_type) &&
    isString(value.connected_at)
  );
}

export function isDeviceListPayload(
  value: unknown,
): value is WSDeviceListPayload {
  return (
    isRecord(value) &&
    value.type === WSMessageType.DEVICE_LIST &&
    Array.isArray(value.devices) &&
    value.devices.every(isDeviceInfo) &&
    isString(value.your_device_id)
  );
}

export function isDeviceCountPayload(
  value: unknown,
): value is WSDeviceCountPayload {
  return (
    isRecord(value) &&
    value.type === WSMessageType.DEVICE_COUNT &&
    typeof value.count === "number" &&
    Number.isFinite(value.count)
  );
}

export function isToastPayload(value: unknown): value is WSToastPayload {
  return (
    isRecord(value) &&
    value.type === WSMessageType.TOAST &&
    isOneOf(TOAST_TYPES, value.toast_type) &&
    isString(value.message) &&
    isString(value.device_name) &&
    isString(value.timestamp)
  );
}

export function isSnippet(value: unknown): value is Snippet {
  return (
    isRecord(value) &&
    isString(value.id) &&
    isString(value.title) &&
    isString(value.content) &&
    isString(value.created_at) &&
    isString(value.updated_at)
  );
}

export function isSnippetPayload(value: unknown): value is WSSnippetPayload {
  return isRecord(value) && isSnippet(value.snippet);
}

export function isSnippetDeletedPayload(
  value: unknown,
): value is WSSnippetDeletedPayload {
  return isRecord(value) && isString(value.snippet_id);
}

export function isFileRequest(value: unknown): value is FileRequest {
  return (
    isRecord(value) &&
    isString(value.id) &&
    isString(value.description) &&
    isString(value.requester_device_id) &&
    isString(value.requester_device_name) &&
    isOneOf(REQUEST_STATUSES, value.status) &&
    isString(value.created_at) &&
    isNullableString(value.fulfilled_by_device_name) &&
    isNullableString(value.fulfilled_file_name) &&
    isNullableString(value.fulfilled_file_path) &&
    isNullableString(value.fulfilled_at)
  );
}

export function isFileRequestPayload(
  value: unknown,
): value is WSFileRequestPayload {
  return isRecord(value) && isFileRequest(value.request);
}

export function isRequestDismissedPayload(
  value: unknown,
): value is WSRequestDismissedPayload {
  return isRecord(value) && isString(value.request_id);
}
