import { useCallback, useEffect, useState } from "react";
import { ClipboardList, LogOut, Monitor, Share2 } from "lucide-react";
import type { FileEntry } from "./types/files.ts";
import { FileType } from "./types/files.ts";
import { FileCategory, getFileCategory } from "./types/fileCategories.ts";
import type { ServerInfo as ServerInfoData } from "./types/serverInfo.ts";
import type { WSToastPayload } from "./types/websocket.ts";
import { WSMessageType, getDeviceName } from "./types/websocket.ts";
import type { ServerMode } from "./types/serverMode.ts";
import {
  fetchFiles,
  downloadFile,
  downloadAsZip,
  deleteFiles,
  renameFile,
  createFolder,
} from "./api/files.ts";
import { fetchServerInfo } from "./api/serverInfo.ts";
import { usePathNavigation } from "./hooks/usePathNavigation.ts";
import { useUpload } from "./hooks/useUpload.ts";
import { useWebSocket } from "./hooks/useWebSocket.ts";
import { useToast } from "./hooks/useToast.ts";
import { useDragDrop } from "./hooks/useDragDrop.ts";
import { useFileSelection } from "./hooks/useFileSelection.ts";
import { useSearch } from "./hooks/useSearch.ts";
import { useSort } from "./hooks/useSort.ts";
import { useTheme, ThemeMode } from "./hooks/useTheme.ts";
import { usePreview } from "./hooks/usePreview.ts";
import { useClipboard } from "./hooks/useClipboard.ts";
import { useFileRequests } from "./hooks/useFileRequests.ts";
import FileList from "./components/FileList.tsx";
import PreviewModal from "./components/PreviewModal.tsx";
import Breadcrumbs from "./components/Breadcrumbs.tsx";
import ServerInfoComponent from "./components/ServerInfo.tsx";
import Toolbar from "./components/Toolbar.tsx";
import BatchToolbar from "./components/BatchToolbar.tsx";
import SearchBar from "./components/SearchBar.tsx";
import FilterChips from "./components/FilterChips.tsx";
import ThemeToggle from "./components/ThemeToggle.tsx";
import ConnectionStatus, { ReconnectingBanner } from "./components/ConnectionStatus.tsx";
import ToastContainer from "./components/ToastContainer.tsx";
import UploadOverlay from "./components/UploadOverlay.tsx";
import UploadPanel from "./components/UploadPanel.tsx";
import ConflictDialog from "./components/ConflictDialog.tsx";
import ConfirmDialog from "./components/ConfirmDialog.tsx";
import CreateFolderDialog from "./components/CreateFolderDialog.tsx";
import ScratchpadPanel from "./components/ScratchpadPanel.tsx";
import ShareLinksPanel from "./components/ShareLinksPanel.tsx";
import DevicesPanel from "./components/DevicesPanel.tsx";
import FileRequestForm from "./components/FileRequestForm.tsx";
import FileRequestBanner from "./components/FileRequestBanner.tsx";
import ModeBadges from "./components/ModeBadges.tsx";

/** Cycle order for theme toggle: SYSTEM -> DARK -> LIGHT -> SYSTEM */
function cycleThemeMode(current: ThemeMode): ThemeMode {
  switch (current) {
    case ThemeMode.SYSTEM:
      return ThemeMode.DARK;
    case ThemeMode.DARK:
      return ThemeMode.LIGHT;
    case ThemeMode.LIGHT:
      return ThemeMode.SYSTEM;
  }
}

/** Stable device name retrieved once from localStorage. */
const deviceName = getDeviceName();

interface AppProps {
  serverMode: ServerMode;
  onLogout: () => void;
}

function App({ serverMode, onLogout }: AppProps) {
  const isReadOnly = serverMode.readOnly;

  const { currentPath, navigateTo } = usePathNavigation();
  const ws = useWebSocket(deviceName);
  const toast = useToast();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [serverInfo, setServerInfo] = useState<ServerInfoData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showShareLinks, setShowShareLinks] = useState<boolean>(false);
  const [showDevices, setShowDevices] = useState<boolean>(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [showCreateFolder, setShowCreateFolder] = useState<boolean>(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  // Search, sort, theme, preview hooks
  const search = useSearch(currentPath);
  const sort = useSort();
  const theme = useTheme();
  const preview = usePreview(currentPath);
  const clipboard = useClipboard(ws.addMessageHandler, ws.removeMessageHandler, ws.sendMessage);

  // Category filter state
  const [activeCategories, setActiveCategories] = useState<Set<FileCategory>>(
    () => new Set([FileCategory.ALL]),
  );

  const loadFiles = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const listing = await fetchFiles(currentPath);
      setFiles(listing.entries);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load files";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [currentPath]);

  const upload = useUpload(currentPath, loadFiles);
  const { isDragging, dragHandlers } = useDragDrop(upload.uploadFiles);
  const selection = useFileSelection(files);
  const fileRequests = useFileRequests(
    ws.addMessageHandler, ws.removeMessageHandler, deviceName, loadFiles,
  );

  // Wire toast handler to WebSocket messages
  useEffect(() => {
    ws.addMessageHandler(WSMessageType.TOAST, (data: unknown) => {
      toast.addToast(data as WSToastPayload);
    });
    return () => {
      ws.removeMessageHandler(WSMessageType.TOAST);
    };
  }, [ws, toast]);

  // Load server info once on mount
  useEffect(() => {
    async function loadServerInfo(): Promise<void> {
      try {
        const info = await fetchServerInfo();
        setServerInfo(info);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load server info";
        setError(message);
      }
    }
    void loadServerInfo();
  }, []);

  // Reload file listing when path changes
  useEffect(() => {
    void loadFiles();
  }, [loadFiles]);

  // --- Category filter ---

  function toggleCategory(category: FileCategory): void {
    if (category === FileCategory.ALL) {
      setActiveCategories(new Set([FileCategory.ALL]));
      return;
    }

    setActiveCategories((prev) => {
      const next = new Set(prev);
      next.delete(FileCategory.ALL);

      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }

      // If nothing is selected, re-activate ALL
      if (next.size === 0) {
        next.add(FileCategory.ALL);
      }
      return next;
    });
  }

  // --- File pipeline: search -> category filter -> sort ---

  const filteredBySearch = search.filterFiles(files);
  const filteredByCategory = activeCategories.has(FileCategory.ALL)
    ? filteredBySearch
    : filteredBySearch.filter(
        (f) =>
          f.type === FileType.DIRECTORY ||
          activeCategories.has(getFileCategory(f.name)),
      );
  const sortedFiles = sort.sortFiles(filteredByCategory);

  // --- Batch operations ---

  function buildSelectedPaths(): string[] {
    return Array.from(selection.selectedNames).map((name) =>
      currentPath === "" ? name : currentPath + "/" + name,
    );
  }

  async function handleBatchDownloadZip(): Promise<void> {
    try {
      await downloadAsZip(buildSelectedPaths());
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "ZIP download failed";
      setError(message);
    }
  }

  function handleBatchDeleteRequest(): void {
    setDeleteTarget(null);
    setShowDeleteConfirm(true);
  }

  async function handleBatchDeleteConfirm(): Promise<void> {
    setShowDeleteConfirm(false);
    try {
      await deleteFiles(buildSelectedPaths());
      selection.clearSelection();
      await loadFiles();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Delete failed";
      setError(message);
    }
  }

  // --- Single-file operations ---

  function handleSingleDeleteRequest(path: string): void {
    setDeleteTarget(path);
    setShowDeleteConfirm(true);
  }

  async function handleSingleDeleteConfirm(): Promise<void> {
    setShowDeleteConfirm(false);
    if (deleteTarget === null) {
      return;
    }
    try {
      await deleteFiles([deleteTarget]);
      setDeleteTarget(null);
      await loadFiles();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Delete failed";
      setError(message);
    }
  }

  function handleDeleteConfirm(): void {
    if (deleteTarget !== null) {
      void handleSingleDeleteConfirm();
    } else {
      void handleBatchDeleteConfirm();
    }
  }

  function handleDeleteCancel(): void {
    setShowDeleteConfirm(false);
    setDeleteTarget(null);
  }

  async function handleRename(path: string, newName: string): Promise<void> {
    try {
      await renameFile(path, newName);
      await loadFiles();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Rename failed";
      setError(message);
    }
  }

  function handleDownload(path: string): void {
    downloadFile(path);
  }

  function handlePreview(file: FileEntry): void {
    preview.openPreview(file);
  }

  // --- Create folder ---

  function handleNewFolderRequest(): void {
    setShowCreateFolder(true);
  }

  async function handleCreateFolder(name: string): Promise<void> {
    setShowCreateFolder(false);
    try {
      await createFolder(currentPath, name);
      await loadFiles();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Create folder failed";
      setError(message);
    }
  }

  function handleCreateFolderCancel(): void {
    setShowCreateFolder(false);
  }

  // --- Delete confirm message ---

  function getDeleteMessage(): string {
    if (deleteTarget !== null) {
      const name = deleteTarget.split("/").pop() ?? deleteTarget;
      return `Are you sure you want to delete "${name}"? This action cannot be undone.`;
    }
    return `Are you sure you want to delete ${String(selection.selectedCount)} selected item(s)? This action cannot be undone.`;
  }

  // --- Theme toggle ---

  function handleThemeToggle(): void {
    theme.setMode(cycleThemeMode(theme.mode));
  }

  return (
    <div
      className="min-h-screen bg-gray-50 dark:bg-gray-900"
      {...(isReadOnly ? {} : dragHandlers)}
    >
      {!isReadOnly && <UploadOverlay visible={isDragging} />}

      <header className="py-6">
        <div className="container mx-auto max-w-4xl px-4 flex items-center justify-between">
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">
              WiFi File Server
            </h1>
            <ModeBadges
              readOnly={serverMode.readOnly}
              passwordProtected={serverMode.passwordRequired}
            />
          </div>
          <div className="flex items-center gap-3">
            <ConnectionStatus isConnected={ws.isConnected} deviceCount={ws.deviceCount} />
            <button
              type="button"
              onClick={() => setShowDevices(true)}
              className="relative p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
              aria-label="Connected devices"
              title="Devices"
            >
              <Monitor className="w-5 h-5" />
              {ws.devices.length > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[1.125rem] h-[1.125rem] flex items-center justify-center rounded-full bg-blue-500 text-white text-[10px] font-bold leading-none px-1">
                  {String(ws.devices.length)}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setShowShareLinks(true)}
              className="p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
              aria-label="Share links"
              title="Share Links"
            >
              <Share2 className="w-5 h-5" />
            </button>
            <button
              type="button"
              onClick={clipboard.togglePanel}
              className="relative p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
              aria-label="Toggle scratchpad"
            >
              <ClipboardList className="w-5 h-5" />
              {clipboard.snippets.length > 0 && (
                <span className="absolute top-0 right-0 w-2 h-2 bg-blue-500 rounded-full" />
              )}
            </button>
            <ThemeToggle
              mode={theme.mode}
              isDark={theme.isDark}
              onToggle={handleThemeToggle}
            />
            {serverMode.passwordRequired && (
              <button
                type="button"
                onClick={() => {
                  void import("./api/auth.ts").then((mod) => mod.logout()).then(onLogout);
                }}
                className="p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
                aria-label="Log out"
                title="Log out"
              >
                <LogOut className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      </header>

      {!ws.isConnected && <ReconnectingBanner />}

      <main className="container mx-auto p-4 max-w-4xl">
        {loading && (
          <p className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</p>
        )}

        {error !== null && (
          <p className="text-center text-red-600 dark:text-red-400 py-4">{error}</p>
        )}

        {!loading && serverInfo !== null && currentPath === "" && (
          <div className="mb-8">
            <ServerInfoComponent info={serverInfo} />
          </div>
        )}

        {!loading && (
          <>
            <Breadcrumbs currentPath={currentPath} onNavigate={navigateTo} />

            <div className="mt-2">
              <SearchBar
                query={search.query}
                onQueryChange={search.setQuery}
                isSearching={search.isSearching}
              />
            </div>

            <FilterChips
              activeCategories={activeCategories}
              onToggleCategory={toggleCategory}
            />

            {isReadOnly ? (
              /* Read-only: show only download-zip batch toolbar when items selected */
              selection.selectedCount > 0 ? (
                <BatchToolbar
                  selectedCount={selection.selectedCount}
                  onDownloadZip={() => void handleBatchDownloadZip()}
                  onDelete={handleBatchDeleteRequest}
                  onClearSelection={selection.clearSelection}
                  readOnly
                />
              ) : null
            ) : (
              /* Normal mode: full toolbar or batch toolbar */
              selection.selectedCount > 0 ? (
                <BatchToolbar
                  selectedCount={selection.selectedCount}
                  onDownloadZip={() => void handleBatchDownloadZip()}
                  onDelete={handleBatchDeleteRequest}
                  onClearSelection={selection.clearSelection}
                />
              ) : (
                <Toolbar
                  onUploadClick={upload.uploadFiles}
                  onNewFolder={handleNewFolderRequest}
                  onRequestFile={fileRequests.toggleForm}
                  currentPath={currentPath}
                />
              )
            )}

            {!isReadOnly && fileRequests.showForm && (
              <FileRequestForm
                onSubmit={(desc) => void fileRequests.submitRequest(desc)}
                onCancel={fileRequests.toggleForm}
              />
            )}

            {!isReadOnly && fileRequests.requests.map((req) => (
              <FileRequestBanner
                key={req.id}
                request={req}
                isOwner={fileRequests.isMyRequest(req)}
                fulfillProgress={fileRequests.fulfillProgress.get(req.id)}
                onFulfill={(id, file) => void fileRequests.fulfillRequest(id, file)}
                onDismiss={(id) => void fileRequests.dismissRequest(id)}
                onDownload={handleDownload}
              />
            ))}

            <FileList
              files={sortedFiles}
              currentPath={currentPath}
              onNavigate={navigateTo}
              selection={{
                selectedNames: selection.selectedNames,
                isAllSelected: selection.isAllSelected,
                isIndeterminate: selection.isIndeterminate,
                toggleSelect: selection.toggleSelect,
                toggleSelectAll: selection.toggleSelectAll,
              }}
              onRename={handleRename}
              onDelete={handleSingleDeleteRequest}
              onDownload={handleDownload}
              onPreview={handlePreview}
              sortField={sort.field}
              sortDirection={sort.direction}
              onSort={sort.toggleSort}
              readOnly={isReadOnly}
            />
          </>
        )}
      </main>

      {/* Upload panel -- floating bottom-right (hidden in read-only) */}
      {!isReadOnly && (
        <UploadPanel
          uploads={upload.uploads}
          collapsed={upload.collapsed}
          onToggleCollapse={upload.toggleCollapsed}
          onClearCompleted={upload.clearCompleted}
          onRetry={upload.retryFailed}
        />
      )}

      {/* Conflict dialog for uploads (hidden in read-only) */}
      {!isReadOnly && upload.pendingConflict !== null && (
        <ConflictDialog
          fileName={upload.pendingConflict.file.name}
          onResolve={upload.resolveConflict}
        />
      )}

      {/* Delete confirmation modal (hidden in read-only) */}
      {!isReadOnly && showDeleteConfirm && (
        <ConfirmDialog
          title="Confirm Delete"
          message={getDeleteMessage()}
          confirmLabel="Delete"
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
        />
      )}

      {/* Create folder dialog (hidden in read-only) */}
      {!isReadOnly && showCreateFolder && (
        <CreateFolderDialog
          onCreateFolder={(name) => void handleCreateFolder(name)}
          onCancel={handleCreateFolderCancel}
        />
      )}

      {/* Toast notifications */}
      <ToastContainer
        toasts={toast.visibleToasts}
        overflowCount={toast.overflowCount}
        onDismiss={toast.dismissToast}
      />

      {/* Devices panel */}
      <DevicesPanel
        isOpen={showDevices}
        onClose={() => setShowDevices(false)}
        devices={ws.devices}
        myDeviceId={ws.myDeviceId}
      />

      {/* Share links panel */}
      <ShareLinksPanel
        isOpen={showShareLinks}
        onClose={() => setShowShareLinks(false)}
      />

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
      {preview.previewFile !== null && (
        <PreviewModal
          file={preview.previewFile}
          files={sortedFiles}
          currentPath={currentPath}
          textContent={preview.textContent}
          isLoadingContent={preview.isLoadingContent}
          contentError={preview.contentError}
          isDark={theme.isDark}
          onClose={preview.closePreview}
          onNavigateFile={preview.openPreview}
        />
      )}
    </div>
  );
}

export default App;
