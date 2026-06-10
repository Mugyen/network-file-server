// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { useUpload } from "./useUpload.ts";
import { ConflictAction, UploadStatus } from "../types/upload.ts";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  uploadWithProgress: vi.fn(),
}));

vi.mock("../api/client.ts", () => {
  class ApiError extends Error {
    readonly status: number;
    readonly body: string;
    constructor(status: number, body: string) {
      super(`API error ${status}`);
      this.name = "ApiError";
      this.status = status;
      this.body = body;
    }
  }
  return { ApiError, uploadWithProgress: mocks.uploadWithProgress };
});

// Built lazily so the mocked ApiError class is the same instance the hook sees.
async function apiError(status: number): Promise<Error> {
  const { ApiError } = await import("../api/client.ts");
  return new ApiError(status, "");
}

/** A deferred promise so a test can hold an upload "in flight". */
function deferred(): { promise: Promise<void>; resolve: () => void; reject: (e: unknown) => void } {
  let resolve!: () => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function fileList(names: string[]): FileList {
  const files = names.map((n) => new File(["x"], n, { type: "text/plain" }));
  const list: Record<number, File> & {
    length: number;
    item: (i: number) => File | null;
    [Symbol.iterator]: () => IterableIterator<File>;
  } = {
    length: files.length,
    item: (i: number) => files[i] ?? null,
    [Symbol.iterator]: () => files[Symbol.iterator](),
  };
  files.forEach((f, i) => {
    list[i] = f;
  });
  return list as unknown as FileList;
}

let onComplete: ReturnType<typeof vi.fn>;
let current: ReturnType<typeof useUpload> | null = null;

function Harness(): null {
  // currentPath stable ("") and a stable onComplete keep the hook callbacks
  // referentially stable across renders (as the real provider does).
  const value = useUpload("", onComplete);
  useEffect(() => {
    current = value;
  });
  return null;
}

function hook(): ReturnType<typeof useUpload> {
  if (current === null) throw new Error("useUpload harness did not render");
  return current;
}

/** Flush microtasks + the queue-processing effect a few times. */
async function flush(): Promise<void> {
  for (let i = 0; i < 4; i++) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

describe("useUpload", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.clearAllMocks();
    current = null;
    onComplete = vi.fn();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.restoreAllMocks();
  });

  async function mount(): Promise<void> {
    await act(async () => {
      root.render(<Harness />);
    });
  }

  it("caps concurrent uploads at 3", async () => {
    const pending = Array.from({ length: 5 }, () => deferred());
    let call = 0;
    mocks.uploadWithProgress.mockImplementation(() => pending[call++].promise);

    await mount();
    act(() => hook().uploadFiles(fileList(["a", "b", "c", "d", "e"])));
    await flush();

    // Only MAX_CONCURRENT (3) of the 5 queued uploads are in flight.
    expect(mocks.uploadWithProgress).toHaveBeenCalledTimes(3);

    // Completing one frees a slot for the next queued upload.
    await act(async () => {
      pending[0].resolve();
      await Promise.resolve();
    });
    await flush();
    expect(mocks.uploadWithProgress).toHaveBeenCalledTimes(4);
  });

  it("calls onUploadComplete after a successful upload", async () => {
    mocks.uploadWithProgress.mockResolvedValue(undefined);
    await mount();
    act(() => hook().uploadFiles(fileList(["ok.txt"])));
    await flush();

    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(hook().uploads[0].status).toBe(UploadStatus.DONE);
  });

  it("surfaces a 409 as a pending conflict; SKIP marks it done", async () => {
    mocks.uploadWithProgress.mockRejectedValue(await apiError(409));
    await mount();
    act(() => hook().uploadFiles(fileList(["dup.txt"])));
    await flush();

    expect(hook().pendingConflict?.status).toBe(UploadStatus.CONFLICT);

    act(() => hook().resolveConflict(ConflictAction.SKIP));
    await flush();
    expect(hook().pendingConflict).toBeNull();
    expect(hook().uploads[0].status).toBe(UploadStatus.DONE);
  });

  it("conflict OVERWRITE re-queues the upload with the chosen action", async () => {
    mocks.uploadWithProgress.mockRejectedValueOnce(await apiError(409));
    mocks.uploadWithProgress.mockResolvedValue(undefined);
    await mount();
    act(() => hook().uploadFiles(fileList(["dup.txt"])));
    await flush();
    expect(hook().pendingConflict).not.toBeNull();

    act(() => hook().resolveConflict(ConflictAction.OVERWRITE));
    await flush();

    expect(hook().uploads[0].status).toBe(UploadStatus.DONE);
    // The retry was sent with the overwrite action.
    const lastCall = mocks.uploadWithProgress.mock.calls.at(-1);
    expect(lastCall?.[2]).toBe(ConflictAction.OVERWRITE);
  });

  it("marks a non-conflict failure FAILED; retryFailed re-queues it", async () => {
    mocks.uploadWithProgress.mockRejectedValueOnce(new Error("network down"));
    mocks.uploadWithProgress.mockResolvedValue(undefined);
    await mount();
    act(() => hook().uploadFiles(fileList(["x.txt"])));
    await flush();

    expect(hook().uploads[0].status).toBe(UploadStatus.FAILED);
    expect(hook().uploads[0].error).toBe("network down");

    act(() => hook().retryFailed(hook().uploads[0].id));
    await flush();
    expect(hook().uploads[0].status).toBe(UploadStatus.DONE);
  });
});
