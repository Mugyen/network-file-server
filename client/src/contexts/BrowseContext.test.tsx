// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, useEffect } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowseProvider, useBrowse } from "./BrowseContext.tsx";
import type { FileEntry } from "../types/files.ts";
import { FileType } from "../types/files.ts";
import { FileCategory } from "../types/fileCategories.ts";

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

function entry(name: string, type: FileType): FileEntry {
  return {
    name,
    size: 1,
    size_display: "1 B",
    type,
    modified: "2026-01-01T00:00:00Z",
    expires_at: null,
  };
}

const dirDocs = entry("docs", FileType.DIRECTORY);
const fileImage = entry("cat.png", FileType.FILE);
const fileText = entry("notes.txt", FileType.FILE);

let current: ReturnType<typeof useBrowse> | null = null;

function Harness(): null {
  const value = useBrowse();
  // Capture outside render (act() flushes effects) to keep render pure.
  useEffect(() => {
    current = value;
  });
  return null;
}

/** Hook result captured after render; throws if the harness never ran. */
function hook(): ReturnType<typeof useBrowse> {
  if (current === null) {
    throw new Error("useBrowse harness did not render");
  }
  return current;
}

/** Wrap children in a fresh QueryClientProvider — the BrowseProvider's
 *  listing query needs one, and per-test isolation avoids cache bleed. */
function withQuery(client: QueryClient, children: ReactNode): ReactNode {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("BrowseContext", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    current = null;
    mocks.fetchFiles.mockResolvedValue({
      path: "",
      entries: [fileText, fileImage, dirDocs],
    });
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
        withQuery(
          queryClient,
          <BrowseProvider>
            <Harness />
          </BrowseProvider>,
        ),
      );
    });
    // Flush React Query's async fetch + the resulting state updates. A few
    // microtask + macrotask turns settle the query from pending to success.
    for (let i = 0; i < 5; i++) {
      await act(async () => {
        await Promise.resolve();
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }

  it("useBrowse throws a typed Error outside the provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => {
      act(() => {
        root.render(<Harness />);
      });
    }).toThrow("useBrowse must be used within a BrowseProvider");
  });

  it("loads the listing on mount and sorts directories first", async () => {
    await mount();

    expect(mocks.fetchFiles).toHaveBeenCalledWith("");
    expect(hook().loading).toBe(false);
    expect(hook().error).toBeNull();
    expect(hook().files).toEqual([fileText, fileImage, dirDocs]);
    expect(hook().sortedFiles.map((f) => f.name)).toEqual([
      "docs",
      "cat.png",
      "notes.txt",
    ]);
  });

  it("category filter keeps directories and toggles back to ALL", async () => {
    await mount();

    act(() => {
      hook().toggleCategory(FileCategory.IMAGES);
    });
    expect(hook().sortedFiles.map((f) => f.name)).toEqual(["docs", "cat.png"]);

    // Deselecting the last category re-activates ALL.
    act(() => {
      hook().toggleCategory(FileCategory.IMAGES);
    });
    expect(hook().activeCategories.has(FileCategory.ALL)).toBe(true);
    expect(hook().sortedFiles).toHaveLength(3);
  });

  it("surfaces a failed delete through the error state", async () => {
    await mount();
    mocks.deleteFiles.mockRejectedValue(new Error("delete exploded"));

    await act(async () => {
      await hook().deletePath("notes.txt");
    });

    expect(mocks.deleteFiles).toHaveBeenCalledWith(["notes.txt"]);
    expect(hook().error).toBe("delete exploded");
    // The listing is not reloaded after a failed delete.
    expect(mocks.fetchFiles).toHaveBeenCalledTimes(1);
  });

  it("reportError surfaces an external failure message", async () => {
    await mount();

    act(() => {
      hook().reportError("server info failed");
    });

    expect(hook().error).toBe("server info failed");
  });

  it("refetches the listing after a successful delete (invalidation)", async () => {
    await mount();
    expect(mocks.fetchFiles).toHaveBeenCalledTimes(1);
    mocks.deleteFiles.mockResolvedValue({ deleted: ["notes.txt"] });

    await act(async () => {
      await hook().deletePath("notes.txt");
    });
    // Let the invalidation-triggered refetch settle.
    for (let i = 0; i < 5; i++) {
      await act(async () => {
        await Promise.resolve();
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }

    expect(mocks.deleteFiles).toHaveBeenCalledWith(["notes.txt"]);
    // The listing was reloaded exactly once via React Query invalidation.
    expect(mocks.fetchFiles).toHaveBeenCalledTimes(2);
    expect(hook().error).toBeNull();
  });
});
