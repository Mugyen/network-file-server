// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import ErrorBoundary from "./ErrorBoundary.tsx";

// React's act() requires this flag outside of a test renderer setup.
declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

/** Child that always throws during render. */
function Bomb(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
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

  it("renders a healthy child normally", () => {
    act(() => {
      root.render(
        <ErrorBoundary label="test">
          <p>healthy child</p>
        </ErrorBoundary>,
      );
    });
    expect(container.textContent).toContain("healthy child");
    expect(container.textContent).not.toContain("Something went wrong");
  });

  it("renders the fallback when a child throws", () => {
    // Silence the expected React error reporting and our own logging.
    const errorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    act(() => {
      root.render(
        <ErrorBoundary label="test">
          <Bomb />
        </ErrorBoundary>,
      );
    });

    expect(container.textContent).toContain("Something went wrong");
    const button = container.querySelector("button");
    expect(button).not.toBeNull();
    expect(button?.textContent).toBe("Reload");
    expect(errorSpy).toHaveBeenCalled();
  });

  it("logs the boundary label with the caught error", () => {
    const errorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    act(() => {
      root.render(
        <ErrorBoundary label="admin">
          <Bomb />
        </ErrorBoundary>,
      );
    });

    const loggedLabel = errorSpy.mock.calls.some(
      (args) => typeof args[0] === "string" && args[0].includes("[admin]"),
    );
    expect(loggedLabel).toBe(true);
  });

  it("isolates the crash: siblings outside the boundary keep rendering", () => {
    const errorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    act(() => {
      root.render(
        <div>
          <p>outside</p>
          <ErrorBoundary label="inner">
            <Bomb />
          </ErrorBoundary>
        </div>,
      );
    });

    expect(container.textContent).toContain("outside");
    expect(container.textContent).toContain("Something went wrong");
    expect(errorSpy).toHaveBeenCalled();
  });
});
