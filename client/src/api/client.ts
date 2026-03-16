import type { ConflictAction } from "../types/upload.ts";
import type { UploadResult } from "../types/upload.ts";
import { getDeviceName } from "../types/websocket.ts";
import { getApiBase, isRemoteMount, getMountPrefix } from "../utils/remoteMount.ts";

const API_BASE = getApiBase();

export class ApiError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string) {
    super(`API error ${status}: ${body}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/**
 * When in remote mount mode, detect HTML error responses from the relay
 * (mount expired/not found/offline) and redirect to the mount root URL
 * so the relay's proper error page renders instead of raw HTML in the SPA.
 */
function handleRelayError(status: number, body: string): never {
  if (isRemoteMount() && body.trimStart().startsWith("<!DOCTYPE")) {
    window.location.replace(`${getMountPrefix()}/`);
    // Throw to stop execution while redirect is pending
    throw new ApiError(status, "Mount unavailable — redirecting...");
  }
  throw new ApiError(status, body);
}

export async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.text();
    handleRelayError(response.status, body);
  }
  const data: T = await response.json();
  return data;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    handleRelayError(response.status, text);
  }
  const data: T = await response.json();
  return data;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    handleRelayError(response.status, text);
  }
  const data: T = await response.json();
  return data;
}

export async function apiDelete<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    handleRelayError(response.status, text);
  }
  const data: T = await response.json();
  return data;
}

/**
 * Upload a single file using XMLHttpRequest for upload progress tracking.
 * fetch() does not support upload progress events -- XHR is required.
 *
 * @throws ApiError on non-2xx response (including 409 for conflicts)
 * @throws Error on network failure
 */
export function uploadWithProgress(
  file: File,
  targetPath: string,
  conflictResolution: ConflictAction | null,
  onProgress: (percent: number) => void,
): Promise<UploadResult[]> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("files", file);

    xhr.upload.addEventListener("progress", (event: ProgressEvent) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const results: UploadResult[] = JSON.parse(xhr.responseText) as UploadResult[];
        resolve(results);
      } else {
        reject(new ApiError(xhr.status, xhr.responseText));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Upload failed: network error"));
    });

    let url = `${API_BASE}/files/upload?path=${encodeURIComponent(targetPath)}`;
    if (conflictResolution !== null) {
      url += `&conflict_resolution=${encodeURIComponent(conflictResolution)}`;
    }

    xhr.open("POST", url);
    const name = getDeviceName();
    xhr.setRequestHeader("X-Device-Name", name);
    xhr.send(formData);
  });
}
