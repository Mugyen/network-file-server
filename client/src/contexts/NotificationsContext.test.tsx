// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import {
  NotificationsProvider,
  useNotifications,
} from "./NotificationsContext.tsx";

// React's act() requires this flag outside of a test renderer setup.
declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let current: ReturnType<typeof useNotifications> | null = null;

function Harness(): null {
  const value = useNotifications();
  // Capture outside render (act() flushes effects) to keep render pure.
  useEffect(() => {
    current = value;
  });
  return null;
}

/** Hook result captured after render; throws if the harness never ran. */
function hook(): ReturnType<typeof useNotifications> {
  if (current === null) {
    throw new Error("useNotifications harness did not render");
  }
  return current;
}

describe("NotificationsContext", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    current = null;
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

  it("useNotifications throws a typed Error outside the provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => {
      act(() => {
        root.render(<Harness />);
      });
    }).toThrow("useNotifications must be used within a NotificationsProvider");
  });

  it("provides toast state and renders dispatched toasts via ToastContainer", () => {
    act(() => {
      root.render(
        <NotificationsProvider>
          <Harness />
        </NotificationsProvider>,
      );
    });

    expect(hook().toasts).toEqual([]);
    expect(hook().overflowCount).toBe(0);

    act(() => {
      hook().addErrorToast("disk full");
    });

    expect(hook().toasts).toHaveLength(1);
    expect(hook().toasts[0].message).toBe("disk full");
    expect(hook().visibleToasts).toHaveLength(1);
    // The provider renders the ToastContainer overlay itself.
    expect(container.textContent).toContain("disk full");
  });

  it("dismissToast removes a toast from state and the DOM", () => {
    act(() => {
      root.render(
        <NotificationsProvider>
          <Harness />
        </NotificationsProvider>,
      );
    });

    act(() => {
      hook().addErrorToast("going away");
    });
    const id = hook().toasts[0].id;

    act(() => {
      hook().dismissToast(id);
    });

    expect(hook().toasts).toEqual([]);
    expect(container.textContent).not.toContain("going away");
  });
});
