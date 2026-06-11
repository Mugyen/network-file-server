import { QueryClient } from "@tanstack/react-query";

/**
 * Shared QueryClient for server-state caching, request deduplication, and
 * invalidation-on-mutation.
 *
 * `staleTime` keeps a just-fetched listing fresh briefly so rapid
 * re-navigations don't refetch; mutations invalidate explicitly. `retry: 0`
 * because the API surfaces typed errors we want to show immediately rather
 * than mask behind silent retries.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      retry: 0,
      refetchOnWindowFocus: false,
    },
  },
});

/** Query keys — centralized so invalidation sites can't typo the key. */
export const queryKeys = {
  files: (path: string): readonly [string, string] => ["files", path],
  filesAll: (): readonly [string] => ["files"],
} as const;
