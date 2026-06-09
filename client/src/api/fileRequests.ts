import type { FileRequest } from "../types/fileRequests.ts";
import { ApiError } from "./client.ts";
import { API_ROUTES } from "./endpoints.ts";
import { getApiBase } from "../utils/remoteMount.ts";

const API_BASE = getApiBase();

/** Fetch all non-dismissed file requests. */
export async function fetchFileRequests(): Promise<FileRequest[]> {
  const response = await fetch(`${API_BASE}${API_ROUTES.fileRequests}/`);
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body);
  }
  const data: FileRequest[] = await response.json();
  return data;
}

/** Create a new file request. */
export async function createFileRequest(
  description: string,
  deviceId: string,
  deviceName: string,
): Promise<FileRequest> {
  const response = await fetch(`${API_BASE}${API_ROUTES.fileRequests}/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Device-Id": deviceId,
      "X-Device-Name": deviceName,
    },
    body: JSON.stringify({ description }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body);
  }
  const data: FileRequest = await response.json();
  return data;
}

/**
 * Fulfill a file request by uploading a file.
 * Uses XHR for upload progress tracking (fetch lacks upload.onprogress).
 */
export function fulfillFileRequest(
  requestId: string,
  file: File,
  deviceName: string,
  onProgress: (percent: number) => void,
): Promise<FileRequest> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.upload.addEventListener("progress", (event: ProgressEvent) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const result: FileRequest = JSON.parse(xhr.responseText) as FileRequest;
        resolve(result);
      } else {
        reject(new ApiError(xhr.status, xhr.responseText));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Fulfill upload failed: network error"));
    });

    xhr.open("POST", `${API_BASE}${API_ROUTES.fileRequests}/${requestId}/fulfill`);
    xhr.setRequestHeader("X-Device-Name", deviceName);
    xhr.send(formData);
  });
}

/** Dismiss a file request (only by the requester). */
export async function dismissFileRequest(
  requestId: string,
  deviceId: string,
): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}${API_ROUTES.fileRequests}/${requestId}`, {
    method: "DELETE",
    headers: { "X-Device-Id": deviceId },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body);
  }
  const data: { status: string } = await response.json();
  return data;
}
