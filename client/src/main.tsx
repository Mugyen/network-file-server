import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import ErrorBoundary from "./components/ErrorBoundary.tsx";
import LoginPage from "./components/LoginPage.tsx";
import DropBoxPage from "./components/DropBoxPage.tsx";
import RelayLoginPage from "./pages/LoginPage.tsx";
import SignupPage from "./pages/SignupPage.tsx";
import AdminDashboard from "./pages/AdminDashboard.tsx";
import Forbidden403 from "./pages/Forbidden403.tsx";
import { fetchServerInfo } from "./api/serverInfo.ts";
import { API_ROUTES } from "./api/endpoints.ts";
import type { ServerMode } from "./types/serverMode.ts";
import { getApiBase } from "./utils/remoteMount.ts";
import { Loader2 } from "lucide-react";

function Root() {
  const [serverMode, setServerMode] = useState<ServerMode | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    async function loadServerMode(): Promise<void> {
      try {
        // Relay account-gate detection: a RESTRICTED, password-less mount
        // 302s to /login (or 401s for XHR). Detect and route to login.
        const probe = await fetch(`${getApiBase()}${API_ROUTES.serverInfo}`, {
          credentials: "include",
          redirect: "manual",
        });
        if (probe.type === "opaqueredirect" || probe.status === 401) {
          const here = window.location.pathname + window.location.search;
          window.location.assign(`/login?next=${encodeURIComponent(here)}`);
          return;
        }

        const info = await fetchServerInfo();
        const mode: ServerMode = {
          readOnly: info.read_only,
          receive: info.receive,
          passwordRequired: info.password_required,
          hostname: info.hostname,
        };
        setServerMode(mode);

        if (!info.password_required) {
          setIsAuthenticated(true);
        } else {
          // Probe a gated endpoint to check if session cookie is still valid
          const probe = await fetch(`${getApiBase()}${API_ROUTES.files}`, { credentials: "include" });
          if (probe.ok) {
            setIsAuthenticated(true);
          }
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load server info";
        setLoadError(message);
      }
    }
    void loadServerMode();
  }, []);

  // Loading state
  if (serverMode === null && loadError === null) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-gray-400 animate-spin" />
      </div>
    );
  }

  // Error state
  if (loadError !== null) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <p className="text-red-600 dark:text-red-400">{loadError}</p>
      </div>
    );
  }

  // Explicit narrowing instead of a non-null assertion: if the loading and
  // error branches above ever change, this fails visibly rather than lying
  // to the type checker.
  if (serverMode === null) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <p className="text-red-600 dark:text-red-400">Failed to determine server mode</p>
      </div>
    );
  }
  const mode = serverMode;

  // Password gate
  if (mode.passwordRequired && !isAuthenticated) {
    return <LoginPage onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  // Receive-only mode -- show drop box
  if (mode.receive) {
    return <DropBoxPage hostname={mode.hostname} />;
  }

  // Normal or read-only mode -- show full app
  return <App serverMode={mode} onLogout={() => setIsAuthenticated(false)} />;
}

/** Relay-served account pages are matched by exact path before the
 *  mount/SPA flow runs. */
function pickRoot() {
  const path = window.location.pathname;
  if (path === "/login")
    return (
      <ErrorBoundary label="login">
        <RelayLoginPage />
      </ErrorBoundary>
    );
  if (path === "/signup")
    return (
      <ErrorBoundary label="signup">
        <SignupPage />
      </ErrorBoundary>
    );
  if (path === "/admin")
    return (
      <ErrorBoundary label="admin">
        <AdminDashboard />
      </ErrorBoundary>
    );
  if (path === "/403")
    return (
      <ErrorBoundary label="403">
        <Forbidden403 />
      </ErrorBoundary>
    );
  return (
    <ErrorBoundary label="root">
      <Root />
    </ErrorBoundary>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>{pickRoot()}</StrictMode>,
);

// Register service worker so the app is installable as a PWA (required for
// Web Share Target on Android). Registered relative to the document URL so it
// works both at the root and under /m/{code}/ when served via the relay.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {
      // Ignore registration failures — the app still works without PWA install.
    });
  });
}
