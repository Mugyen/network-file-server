import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import type { ServerInfo as ServerInfoData } from "./types/serverInfo.ts";
import { WSMessageType, getDeviceId, getDeviceName } from "./types/websocket.ts";
import type { ServerMode } from "./types/serverMode.ts";
import { fetchServerInfo } from "./api/serverInfo.ts";
import { useWebSocket } from "./hooks/useWebSocket.ts";
import { useTheme, cycleThemeMode } from "./hooks/useTheme.ts";
import { useClipboard } from "./hooks/useClipboard.ts";
import { useFileRequests } from "./hooks/useFileRequests.ts";
import { useMountStatus, MountStatus } from "./hooks/useMountStatus.ts";
import {
  NotificationsProvider,
  useNotifications,
} from "./contexts/NotificationsContext.tsx";
import { BrowseProvider, useBrowse } from "./contexts/BrowseContext.tsx";
import { UploadProvider, useUploads } from "./contexts/UploadContext.tsx";
import PreviewModal from "./components/PreviewModal.tsx";
import ServerInfoComponent from "./components/ServerInfo.tsx";
import { ReconnectingBanner } from "./components/ConnectionStatus.tsx";
import { MountStatusOverlay } from "./components/MountStatusOverlay.tsx";
import UploadOverlay from "./components/UploadOverlay.tsx";
import ScratchpadPanel from "./components/ScratchpadPanel.tsx";
import ModeBadges from "./components/ModeBadges.tsx";
import FileBrowserSection from "./components/FileBrowserSection.tsx";
import HeaderActions from "./components/HeaderActions.tsx";
import UploadWidgets from "./components/UploadWidgets.tsx";
import { isToastPayload } from "./utils/wsGuards.ts";
import { isRemoteMount } from "./utils/remoteMount.ts";

/** Stable device name (cosmetic) and device ID (identity), each persisted once. */
const deviceName = getDeviceName();
const deviceId = getDeviceId();

interface AppProps {
  serverMode: ServerMode;
  onLogout: () => void;
}

/**
 * Inner app shell. Lives inside the providers so it can consume the
 * notifications/browse/upload contexts; keeps the WS, mount-status,
 * clipboard, and file-request wiring that spans those slices.
 */
function AppContent({ serverMode, onLogout }: AppProps): ReactElement {
  const isReadOnly = serverMode.readOnly;

  const ws = useWebSocket(deviceId, deviceName);
  const toast = useNotifications();
  const browse = useBrowse();
  const uploads = useUploads();
  const mountStatus = useMountStatus();
  const theme = useTheme();
  const [serverInfo, setServerInfo] = useState<ServerInfoData | null>(null);
  // Stable callbacks from the context/hook slices (identities survive renders).
  const { loadFiles, reportError } = browse;
  const { onRecoveryRef, triggerPoll } = mountStatus;
  const clipboard = useClipboard(
    ws.addMessageHandler, ws.removeMessageHandler, ws.sendMessage, toast.addErrorToast,
  );
  const fileRequests = useFileRequests(
    ws.addMessageHandler, ws.removeMessageHandler, deviceId, deviceName, loadFiles,
  );

  // Wire mount status recovery to file list refresh
  useEffect(() => {
    onRecoveryRef.current = loadFiles;
  }, [onRecoveryRef, loadFiles]);

  // Trigger immediate status poll when WebSocket disconnects in remote mode
  useEffect(() => {
    if (!ws.isConnected && isRemoteMount()) {
      triggerPoll();
    }
  }, [ws.isConnected, triggerPoll]);

  // Wire toast handler to WebSocket messages (payload runtime-guarded)
  useEffect(() => {
    ws.addMessageHandler(WSMessageType.TOAST, (data: unknown) => {
      if (!isToastPayload(data)) {
        console.error("Malformed WS message", WSMessageType.TOAST, data);
        return;
      }
      toast.addToast(data);
    });
    return () => {
      ws.removeMessageHandler(WSMessageType.TOAST);
    };
  }, [ws, toast]);

  // Load server info once on mount (reportError is stable across renders)
  useEffect(() => {
    async function loadServerInfo(): Promise<void> {
      try {
        const info = await fetchServerInfo();
        setServerInfo(info);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load server info";
        reportError(message);
      }
    }
    void loadServerInfo();
  }, [reportError]);

  // --- Theme toggle ---

  function handleThemeToggle(): void {
    theme.setMode(cycleThemeMode(theme.mode));
  }

  return (
    <div
      className="min-h-screen bg-gray-50 dark:bg-gray-900"
      {...(isReadOnly ? {} : uploads.dragHandlers)}
    >
      {!isReadOnly && <UploadOverlay visible={uploads.isDragging} />}

      <header className="py-6">
        <div className="container mx-auto max-w-4xl px-4 flex items-center justify-between">
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">
              Network File Server
            </h1>
            <ModeBadges
              readOnly={serverMode.readOnly}
              passwordProtected={serverMode.passwordRequired}
              remote={isRemoteMount()}
            />
          </div>
          <HeaderActions
            isConnected={ws.isConnected}
            deviceCount={ws.deviceCount}
            devices={ws.devices}
            myDeviceId={ws.myDeviceId}
            onScratchpadToggle={clipboard.togglePanel}
            snippetCount={clipboard.snippets.length}
            themeMode={theme.mode}
            isDark={theme.isDark}
            onThemeToggle={handleThemeToggle}
            passwordRequired={serverMode.passwordRequired}
            onLogout={onLogout}
          />
        </div>
      </header>

      {!ws.isConnected && !isRemoteMount() && <ReconnectingBanner />}

      <MountStatusOverlay status={isRemoteMount() ? mountStatus.status : MountStatus.ONLINE}>
      <main className="container mx-auto p-4 max-w-4xl">
        {browse.loading && (
          <p className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</p>
        )}

        {browse.error !== null && (
          <p className="text-center text-red-600 dark:text-red-400 py-4">{browse.error}</p>
        )}

        {!browse.loading && serverInfo !== null && browse.currentPath === "" && (
          <div className="mb-8">
            <ServerInfoComponent info={serverInfo} />
          </div>
        )}

        <FileBrowserSection readOnly={isReadOnly} fileRequests={fileRequests} />
      </main>
      </MountStatusOverlay>

      {/* Upload panel + conflict dialog (hidden in read-only) */}
      {!isReadOnly && <UploadWidgets />}

      {/* Scratchpad panel — read-only hides write actions */}
      <ScratchpadPanel
        isOpen={clipboard.isOpen}
        snippets={clipboard.snippets}
        isLoading={clipboard.isLoading}
        onClose={clipboard.togglePanel}
        onAddSnippet={clipboard.addSnippet}
        onUpdateContent={clipboard.updateContent}
        onUpdateTitle={clipboard.updateTitle}
        onDeleteSnippet={clipboard.removeSnippet}
        readOnly={isReadOnly}
      />

      {/* File preview modal */}
      {browse.preview.previewFile !== null && (
        <PreviewModal
          file={browse.preview.previewFile}
          files={browse.sortedFiles}
          currentPath={browse.currentPath}
          textContent={browse.preview.textContent}
          isLoadingContent={browse.preview.isLoadingContent}
          contentError={browse.preview.contentError}
          isDark={theme.isDark}
          onClose={browse.preview.closePreview}
          onNavigateFile={browse.preview.openPreview}
        />
      )}
    </div>
  );
}

/** Composes the context providers around the app shell. */
function App({ serverMode, onLogout }: AppProps): ReactElement {
  return (
    <NotificationsProvider>
      <BrowseProvider>
        <UploadProvider>
          <AppContent serverMode={serverMode} onLogout={onLogout} />
        </UploadProvider>
      </BrowseProvider>
    </NotificationsProvider>
  );
}

export default App;
