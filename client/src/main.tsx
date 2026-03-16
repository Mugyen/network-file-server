import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import LoginPage from "./components/LoginPage.tsx";
import DropBoxPage from "./components/DropBoxPage.tsx";
import { fetchServerInfo } from "./api/serverInfo.ts";
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
          const probe = await fetch(`${getApiBase()}/files`, { credentials: "include" });
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

  // serverMode is guaranteed non-null here
  const mode = serverMode!;

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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
