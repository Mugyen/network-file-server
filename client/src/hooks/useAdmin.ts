import { useCallback, useEffect, useState } from "react";
import { accounts, AccountApiError } from "../api/accounts.ts";

/** A user account as listed on the admin dashboard. */
export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  is_active: boolean;
}

/** A permission group as listed on the admin dashboard. */
export interface AdminGroup {
  id: number;
  name: string;
}

/** A mount-access request as listed on the admin dashboard. */
export interface AccessRequest {
  id: number;
  code: string;
  user_id: number;
  username: string | null;
  status: string;
}

/** Kind of member that can be added to a group. */
export const GroupMemberType = {
  USER: "user",
  GROUP: "group",
} as const;

export type GroupMemberType =
  (typeof GroupMemberType)[keyof typeof GroupMemberType];

/** Admin decision on an access request. */
export const RequestAction = {
  APPROVE: "approve",
  DENY: "deny",
} as const;

export type RequestAction = (typeof RequestAction)[keyof typeof RequestAction];

/** Mount role granted when approving an access request. */
export const MountRole = {
  READ: "read",
  WRITE: "write",
  RECEIVE: "receive",
} as const;

export type MountRole = (typeof MountRole)[keyof typeof MountRole];

interface UseAdminResult {
  /** Bootstrap (identity check + first load) has finished. */
  ready: boolean;
  /** Current session is not an admin (or bootstrap failed). */
  denied: boolean;
  users: AdminUser[];
  groups: AdminGroup[];
  requests: AccessRequest[];
  /** Last action/refresh error, or null after a successful action. */
  notice: string | null;
  /** Re-fetch all lists; failures land in `notice` instead of vanishing. */
  refresh: () => Promise<void>;
  setUserActive: (userId: number, isActive: boolean) => Promise<void>;
  /** Resolves true when the group was created and lists refreshed. */
  createGroup: (name: string) => Promise<boolean>;
  deleteGroup: (groupId: number) => Promise<void>;
  /**
   * Throws AccountApiError on failure so callers can show inline feedback
   * (the per-group row message), unlike the guarded mutations above.
   */
  addGroupMember: (
    groupId: number,
    memberType: GroupMemberType,
    memberRef: string,
  ) => Promise<void>;
  resolveRequest: (
    requestId: number,
    action: RequestAction,
    role: MountRole | null,
  ) => Promise<void>;
}

/** Async no-op for guarded refresh-only runs (avoids empty-function lint). */
const NOOP_ASYNC = (): Promise<void> => Promise.resolve();

/**
 * Owns admin dashboard data (users, groups, access requests), the refresh
 * cycle, and all mutations. The component keeps only UI state.
 */
export function useAdmin(): UseAdminResult {
  const [ready, setReady] = useState<boolean>(false);
  const [denied, setDenied] = useState<boolean>(false);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [groups, setGroups] = useState<AdminGroup[]>([]);
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshOrThrow = useCallback(async (): Promise<void> => {
    setUsers(await accounts.listUsers());
    setGroups(await accounts.listGroups());
    setRequests(await accounts.listRequests());
  }, []);

  /**
   * Run a mutation, then refresh. Success clears the notice; any failure
   * (mutation or refresh) is logged and surfaced as the notice. Returns
   * whether everything succeeded.
   */
  const guarded = useCallback(
    async (fn: () => Promise<void>): Promise<boolean> => {
      try {
        await fn();
        await refreshOrThrow();
        setNotice(null);
        return true;
      } catch (err: unknown) {
        // Converted to UI error state; logged with context (not swallowed).
        console.error("Admin action failed:", err);
        setNotice(err instanceof AccountApiError ? err.message : "Action failed");
        return false;
      }
    },
    [refreshOrThrow],
  );

  useEffect(() => {
    void (async () => {
      try {
        const me = await accounts.me();
        if (!me.is_admin) {
          setDenied(true);
          return;
        }
        await refreshOrThrow();
      } catch (err: unknown) {
        if (err instanceof AccountApiError && err.status === 401) {
          window.location.assign("/login?next=/admin");
          return;
        }
        // Any other bootstrap failure renders the access-denied panel.
        console.error("Admin bootstrap failed:", err);
        setDenied(true);
      } finally {
        setReady(true);
      }
    })();
  }, [refreshOrThrow]);

  const refresh = useCallback(async (): Promise<void> => {
    await guarded(NOOP_ASYNC);
  }, [guarded]);

  const setUserActive = useCallback(
    async (userId: number, isActive: boolean): Promise<void> => {
      await guarded(async () => {
        await accounts.setUserActive(userId, isActive);
      });
    },
    [guarded],
  );

  const createGroup = useCallback(
    async (name: string): Promise<boolean> => {
      return guarded(async () => {
        await accounts.createGroup(name);
      });
    },
    [guarded],
  );

  const deleteGroup = useCallback(
    async (groupId: number): Promise<void> => {
      await guarded(async () => {
        await accounts.deleteGroup(groupId);
      });
    },
    [guarded],
  );

  const addGroupMember = useCallback(
    async (
      groupId: number,
      memberType: GroupMemberType,
      memberRef: string,
    ): Promise<void> => {
      // Let the mutation error propagate for inline per-row feedback;
      // the follow-up refresh reuses guarded semantics for its own errors.
      await accounts.addGroupMember(groupId, memberType, memberRef);
      await guarded(NOOP_ASYNC);
    },
    [guarded],
  );

  const resolveRequest = useCallback(
    async (
      requestId: number,
      action: RequestAction,
      role: MountRole | null,
    ): Promise<void> => {
      await guarded(async () => {
        await accounts.resolveRequest(requestId, action, role);
      });
    },
    [guarded],
  );

  return {
    ready,
    denied,
    users,
    groups,
    requests,
    notice,
    refresh,
    setUserActive,
    createGroup,
    deleteGroup,
    addGroupMember,
    resolveRequest,
  };
}
