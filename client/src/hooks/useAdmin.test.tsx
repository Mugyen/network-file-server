// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import {
  GroupMemberType,
  MountRole,
  RequestAction,
  useAdmin,
} from "./useAdmin.ts";
import { AccountApiError } from "../api/accounts.ts";

// React's act() requires this flag outside of a test renderer setup.
declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  me: vi.fn(),
  listUsers: vi.fn(),
  listGroups: vi.fn(),
  listRequests: vi.fn(),
  setUserActive: vi.fn(),
  createGroup: vi.fn(),
  deleteGroup: vi.fn(),
  addGroupMember: vi.fn(),
  resolveRequest: vi.fn(),
}));

vi.mock("../api/accounts.ts", () => {
  class AccountApiError extends Error {
    readonly status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "AccountApiError";
      this.status = status;
    }
  }
  return { AccountApiError, accounts: mocks };
});

const adminUser = { id: 1, username: "root", email: null, is_active: true };
const group = { id: 10, name: "staff" };
const request = {
  id: 5,
  code: "abc123",
  user_id: 2,
  username: "alice",
  status: "pending",
};

let current: ReturnType<typeof useAdmin> | null = null;

function Harness(): null {
  const value = useAdmin();
  // Capture outside render (act() flushes effects) to keep render pure.
  useEffect(() => {
    current = value;
  });
  return null;
}

/** Hook results captured after bootstrap; throws if the harness never ran. */
function hook(): ReturnType<typeof useAdmin> {
  if (current === null) {
    throw new Error("useAdmin harness did not render");
  }
  return current;
}

describe("useAdmin", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.clearAllMocks();
    current = null;
    // Defaults: an admin session with one of everything.
    mocks.me.mockResolvedValue({ user_id: 1, username: "root", is_admin: true });
    mocks.listUsers.mockResolvedValue([adminUser]);
    mocks.listGroups.mockResolvedValue([group]);
    mocks.listRequests.mockResolvedValue([request]);
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
      root.render(<Harness />);
    });
    // Flush the bootstrap's chained awaits (me -> users -> groups -> requests).
    await act(async () => {
      await Promise.resolve();
    });
  }

  it("loads users, groups, and requests for an admin", async () => {
    await mount();
    expect(hook().ready).toBe(true);
    expect(hook().denied).toBe(false);
    expect(hook().users).toEqual([adminUser]);
    expect(hook().groups).toEqual([group]);
    expect(hook().requests).toEqual([request]);
    expect(hook().notice).toBeNull();
  });

  it("denies non-admin sessions without fetching lists", async () => {
    mocks.me.mockResolvedValue({ user_id: 2, username: "bob", is_admin: false });
    await mount();
    expect(hook().ready).toBe(true);
    expect(hook().denied).toBe(true);
    expect(mocks.listUsers).not.toHaveBeenCalled();
  });

  it("denies when bootstrap fails with a non-401 error", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    mocks.me.mockRejectedValue(new AccountApiError(500, "boom"));
    await mount();
    expect(hook().ready).toBe(true);
    expect(hook().denied).toBe(true);
    expect(errorSpy).toHaveBeenCalled();
  });

  it("runs a guarded mutation and refreshes on success", async () => {
    await mount();
    mocks.setUserActive.mockResolvedValue(undefined);
    mocks.listUsers.mockResolvedValue([{ ...adminUser, is_active: false }]);

    await act(async () => {
      await hook().setUserActive(1, false);
    });

    expect(mocks.setUserActive).toHaveBeenCalledWith(1, false);
    expect(hook().users[0].is_active).toBe(false);
    expect(hook().notice).toBeNull();
  });

  it("surfaces a guarded mutation failure as the notice", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    await mount();
    mocks.resolveRequest.mockRejectedValue(new AccountApiError(409, "already resolved"));

    await act(async () => {
      await hook().resolveRequest(5, RequestAction.APPROVE, MountRole.READ);
    });

    expect(hook().notice).toBe("already resolved");
    expect(errorSpy).toHaveBeenCalled();
  });

  it("createGroup reports success so the caller can clear its input", async () => {
    await mount();
    mocks.createGroup.mockResolvedValue({ id: 11, name: "new" });

    let created = false;
    await act(async () => {
      created = await hook().createGroup("new");
    });

    expect(created).toBe(true);
    expect(mocks.createGroup).toHaveBeenCalledWith("new");
  });

  it("createGroup reports failure and sets the notice", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    await mount();
    mocks.createGroup.mockRejectedValue(new AccountApiError(409, "duplicate"));

    let created = true;
    await act(async () => {
      created = await hook().createGroup("staff");
    });

    expect(created).toBe(false);
    expect(hook().notice).toBe("duplicate");
    expect(errorSpy).toHaveBeenCalled();
  });

  it("addGroupMember rethrows so the row can show inline feedback", async () => {
    await mount();
    mocks.addGroupMember.mockRejectedValue(new AccountApiError(404, "no such user"));

    await expect(
      hook().addGroupMember(10, GroupMemberType.USER, "ghost"),
    ).rejects.toThrow("no such user");
    // Failed adds must not trigger a refresh.
    expect(mocks.listUsers).toHaveBeenCalledTimes(1);
  });

  it("refresh surfaces fetch failures via the notice", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    await mount();
    mocks.listUsers.mockRejectedValue(new AccountApiError(503, "relay down"));

    await act(async () => {
      await hook().refresh();
    });

    expect(hook().notice).toBe("relay down");
    expect(errorSpy).toHaveBeenCalled();
  });
});
