import type { ServerInfo } from "../types/serverInfo.ts";
import { apiFetch } from "./client.ts";

export function fetchServerInfo(): Promise<ServerInfo> {
  return apiFetch<ServerInfo>("/server-info");
}
