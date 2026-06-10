/**
 * Top-level app-mode routing.
 *
 * One bundle serves several surfaces: the relay's account pages
 * (/login, /signup, /admin, /403) and the file-server SPA (everything else,
 * including the relay mount path /m/{code}/). `resolveAppMode` is the single
 * decision point that maps a pathname to a mode, replacing the former
 * scattered if-chain in main.tsx.
 *
 * The SPA's *internal* server detection (LAN vs relay-auth vs password vs
 * receive) is an async probe and lives in main.tsx's Root component — that is
 * a runtime capability check, not a static route, so it stays separate.
 */

// Const-object "enum" (the codebase convention under erasableSyntaxOnly,
// matching FileType / RequestStatus) — a real TS `enum` is disallowed.
export const AppMode = {
  /** Relay account login page (/login). */
  RelayLogin: "relay-login",
  /** Relay account signup page (/signup). */
  RelaySignup: "relay-signup",
  /** Relay admin dashboard (/admin). */
  RelayAdmin: "relay-admin",
  /** Relay 403 page (/403). */
  Relay403: "relay-403",
  /** The file-server SPA (LAN root or relay mount /m/{code}/). */
  Spa: "spa",
} as const;

export type AppMode = (typeof AppMode)[keyof typeof AppMode];

const _EXACT_PATH_MODES: ReadonlyMap<string, AppMode> = new Map([
  ["/login", AppMode.RelayLogin],
  ["/signup", AppMode.RelaySignup],
  ["/admin", AppMode.RelayAdmin],
  ["/403", AppMode.Relay403],
]);

/**
 * Resolve the app mode for a given pathname.
 *
 * Relay account pages are matched by exact path; everything else (including
 * the relay mount path /m/{code}/...) is the SPA.
 */
export function resolveAppMode(pathname: string): AppMode {
  return _EXACT_PATH_MODES.get(pathname) ?? AppMode.Spa;
}
