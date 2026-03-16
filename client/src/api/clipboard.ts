import type { Snippet } from "../types/clipboard.ts";
import { apiFetch, apiPost, apiPatch } from "./client.ts";
import { getApiBase } from "../utils/remoteMount.ts";

/** Fetch all clipboard snippets. */
export function fetchSnippets(): Promise<Snippet[]> {
  return apiFetch<Snippet[]>("/clipboard/");
}

/** Create a new snippet with the given title. */
export function createSnippet(title: string): Promise<Snippet> {
  return apiPost<Snippet>("/clipboard/", { title });
}

/** Update a snippet's title via REST. */
export function updateSnippetTitle(
  snippetId: string,
  title: string,
): Promise<Snippet> {
  return apiPatch<Snippet>(`/clipboard/${snippetId}`, { title });
}

/** Delete a snippet by ID. Uses fetch DELETE with empty body. */
export async function deleteSnippet(
  snippetId: string,
): Promise<{ status: string }> {
  const response = await fetch(`${getApiBase()}/clipboard/${snippetId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Delete failed: ${body}`);
  }
  return response.json() as Promise<{ status: string }>;
}
