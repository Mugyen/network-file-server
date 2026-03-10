import { apiPost } from "./client.ts";

/** POST /api/auth/login -- sets session cookie on success, throws ApiError on 401. */
export function login(password: string): Promise<void> {
  return apiPost<{ status: string }>("/auth/login", { password }).then(
    () => undefined,
  );
}

/** POST /api/auth/logout -- clears session cookie. */
export function logout(): Promise<void> {
  return apiPost<{ status: string }>("/auth/logout", {}).then(
    () => undefined,
  );
}
