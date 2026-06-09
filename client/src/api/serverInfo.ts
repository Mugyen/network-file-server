import type { ServerInfo } from "../types/serverInfo.ts";
import { apiFetch } from "./client.ts";
import { API_ROUTES } from "./endpoints.ts";

export function fetchServerInfo(): Promise<ServerInfo> {
  return apiFetch<ServerInfo>(API_ROUTES.serverInfo);
}
