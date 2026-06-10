// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowseProvider } from "./BrowseContext.tsx";
import { UploadProvider, useUploads } from "./UploadContext.tsx";

// React's act() requires this flag outside of a test renderer setup.
declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  fetchFiles: vi.fn(),
  downloadFile: vi.fn(),
  downloadAsZip: vi.fn(),
  deleteFiles: vi.fn(),
  renameFile: vi.fn(),
  createFolder: vi.fn(),
  searchFiles: vi.fn(),
}));

vi.mock("../api/files.ts", () => mocks);

let current: ReturnType<typeof useUploads> | null = null;

function Harness(): null {
  const value = useUploads();
  // Capture outside render (act() flushes effects) to keep render pure.
  useEffect(() => {
    current = value;
  });
  return null;
}

/** Hook result captured after render; throws if the harness never ran. */
function hook(): ReturnType<typeof useUploads> {
  if (current === null) {
    throw new Error("useUploads harness did not render");
  }
  return current;
}

/** Minimal stand-in for a React drag event (only preventDefault is used). */
function dragEvent(): React.DragEvent {
  return { preventDefault: () => undefined } as unknown as React.DragEvent;
}

describe("UploadContext", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    current = null;
    mocks.fetchFiles.mockResolvedValue({ path: "", entries: [] });
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  async function mount(): Promise<void> {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <BrowseProvider>
            <UploadProvider>
              <Harness />
            </UploadProvider>
          </BrowseProvider>
        </QueryClientProvider>,
      );
    });
  }

  it("useUploads throws a typed Error outside the provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => {
      act(() => {
        root.render(<Harness />);
      });
    }).toThrow("useUploads must be used within an UploadProvider");
  });

  it("UploadProvider requires an enclosing BrowseProvider", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => {
      act(() => {
        root.render(
          <UploadProvider>
            <Harness />
          </UploadProvider>,
        );
      });
    }).toThrow("useBrowse must be used within a BrowseProvider");
  });

  it("provides the upload slice with an idle initial state", async () => {
    await mount();

    expect(hook().uploads).toEqual([]);
    expect(hook().pendingConflict).toBeNull();
    expect(hook().isUploading).toBe(false);
    expect(hook().isDragging).toBe(false);
    expect(typeof hook().uploadFiles).toBe("function");
  });

  it("tracks drag state through the drag handlers", async () => {
    await mount();

    act(() => {
      hook().dragHandlers.onDragEnter(dragEvent());
    });
    expect(hook().isDragging).toBe(true);

    act(() => {
      hook().dragHandlers.onDragLeave(dragEvent());
    });
    expect(hook().isDragging).toBe(false);
  });
});
