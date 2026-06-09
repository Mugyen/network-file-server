import type { Snippet } from "../types/clipboard.ts";
import { apiDeleteNoBody, apiFetch, apiPatch, apiPost } from "./client.ts";
import { API_ROUTES } from "./endpoints.ts";

/** Fetch all clipboard snippets. */
export function fetchSnippets(): Promise<Snippet[]> {
  return apiFetch<Snippet[]>(`${API_ROUTES.clipboard}/`);
}

/** Create a new snippet with the given title. */
export function createSnippet(title: string): Promise<Snippet> {
  return apiPost<Snippet>(`${API_ROUTES.clipboard}/`, { title });
}

/** Update a snippet's title via REST. */
export function updateSnippetTitle(
  snippetId: string,
  title: string,
): Promise<Snippet> {
  return apiPatch<Snippet>(`${API_ROUTES.clipboard}/${snippetId}`, { title });
}

/** Delete a snippet by ID. The success reply carries no payload we need. */
export function deleteSnippet(snippetId: string): Promise<void> {
  return apiDeleteNoBody(`${API_ROUTES.clipboard}/${snippetId}`);
}
