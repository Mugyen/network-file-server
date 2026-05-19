/**
 * Relay account API client.
 *
 * These endpoints live at the RELAY ROOT (not under a mount prefix), so
 * they use absolute same-origin paths and do NOT go through getApiBase().
 */

export class AccountApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "AccountApiError";
    this.status = status;
  }
}

async function req<T>(
  method: string,
  path: string,
  body: unknown | null,
): Promise<T> {
  const init: RequestInit = { method, credentials: "include" };
  if (body !== null) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const j = (await res.json()) as { detail?: string; error?: string };
      detail = j.detail ?? j.error ?? detail;
    } catch {
      /* non-JSON body */
    }
    throw new AccountApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface Identity {
  user_id: number;
  username: string;
  is_admin: boolean;
}

export const accounts = {
  signup: (username: string, password: string, email: string | null) =>
    req<{ id: number; username: string }>("POST", "/auth/signup", {
      username,
      password,
      email,
    }),
  login: (username: string, password: string) =>
    req<{ username: string; is_admin: boolean }>("POST", "/auth/login", {
      username,
      password,
    }),
  logout: () => req<{ status: string }>("POST", "/auth/logout", {}),
  me: () => req<Identity>("GET", "/auth/me", null),

  // Admin
  listUsers: () =>
    req<
      Array<{
        id: number;
        username: string;
        email: string | null;
        is_active: boolean;
      }>
    >("GET", "/admin/users", null),
  setUserActive: (userId: number, isActive: boolean) =>
    req("POST", `/admin/users/${userId}/active`, { is_active: isActive }),
  listGroups: () =>
    req<Array<{ id: number; name: string }>>("GET", "/admin/groups", null),
  createGroup: (name: string) =>
    req<{ id: number; name: string }>("POST", "/admin/groups", { name }),
  deleteGroup: (groupId: number) =>
    req("DELETE", `/admin/groups/${groupId}`, null),
  listGroupMembers: (groupId: number) =>
    req<Array<{ member_type: string; member_id: number }>>(
      "GET",
      `/admin/groups/${groupId}/members`,
      null,
    ),
  addGroupMember: (
    groupId: number,
    memberType: "user" | "group",
    memberRef: string,
  ) =>
    req("POST", `/admin/groups/${groupId}/members`, {
      member_type: memberType,
      member_ref: memberRef,
    }),

  // Access requests
  createRequest: (code: string) =>
    req<{ id: number; status: string }>("POST", "/requests", { code }),
  listRequests: () =>
    req<
      Array<{
        id: number;
        code: string;
        user_id: number;
        username: string | null;
        status: string;
      }>
    >("GET", "/requests", null),
  resolveRequest: (
    id: number,
    action: "approve" | "deny",
    role: "read" | "write" | "receive" | null,
  ) =>
    req<{ status: string }>("POST", `/requests/${id}/resolve`, {
      action,
      role,
    }),
};
