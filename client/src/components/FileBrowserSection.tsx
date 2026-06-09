import { useState } from "react";
import type { ReactElement } from "react";
import type { FileEntry } from "../types/files.ts";
import { useBrowse } from "../contexts/BrowseContext.tsx";
import { useUploads } from "../contexts/UploadContext.tsx";
import { useFileRequests } from "../hooks/useFileRequests.ts";
import Breadcrumbs from "./Breadcrumbs.tsx";
import SearchBar from "./SearchBar.tsx";
import FilterChips from "./FilterChips.tsx";
import Toolbar from "./Toolbar.tsx";
import BatchToolbar from "./BatchToolbar.tsx";
import FileRequestForm from "./FileRequestForm.tsx";
import FileRequestBanner from "./FileRequestBanner.tsx";
import FileList from "./FileList.tsx";
import ConfirmDialog from "./ConfirmDialog.tsx";
import CreateFolderDialog from "./CreateFolderDialog.tsx";

interface FileBrowserSectionProps {
  readOnly: boolean;
  /** File requests stay wired in App (they need the WS handlers). */
  fileRequests: ReturnType<typeof useFileRequests>;
}

/**
 * The browse surface inside <main>: breadcrumbs, search, filters,
 * toolbars, file-request banners, and the file list. Owns the
 * delete-confirm and create-folder dialogs.
 */
function FileBrowserSection({
  readOnly,
  fileRequests,
}: FileBrowserSectionProps): ReactElement {
  const browse = useBrowse();
  const uploads = useUploads();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [showCreateFolder, setShowCreateFolder] = useState<boolean>(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const { selection } = browse;

  // --- Delete confirm dialog ---

  function handleBatchDeleteRequest(): void {
    setDeleteTarget(null);
    setShowDeleteConfirm(true);
  }

  function handleSingleDeleteRequest(path: string): void {
    setDeleteTarget(path);
    setShowDeleteConfirm(true);
  }

  function handleDeleteConfirm(): void {
    setShowDeleteConfirm(false);
    if (deleteTarget !== null) {
      void browse.deletePath(deleteTarget);
      setDeleteTarget(null);
    } else {
      void browse.deleteSelected();
    }
  }

  function handleDeleteCancel(): void {
    setShowDeleteConfirm(false);
    setDeleteTarget(null);
  }

  function getDeleteMessage(): string {
    if (deleteTarget !== null) {
      const name = deleteTarget.split("/").pop() ?? deleteTarget;
      return `Are you sure you want to delete "${name}"? This action cannot be undone.`;
    }
    return `Are you sure you want to delete ${String(selection.selectedCount)} selected item(s)? This action cannot be undone.`;
  }

  // --- Create folder dialog ---

  function handleNewFolderRequest(): void {
    setShowCreateFolder(true);
  }

  function handleCreateFolder(name: string): void {
    setShowCreateFolder(false);
    void browse.createFolderInCurrent(name);
  }

  function handleCreateFolderCancel(): void {
    setShowCreateFolder(false);
  }

  // --- Preview ---

  function handlePreview(file: FileEntry): void {
    browse.preview.openPreview(file);
  }

  return (
    <>
      {!browse.loading && (
        <>
          <Breadcrumbs
            currentPath={browse.currentPath}
            onNavigate={browse.navigateTo}
          />

          <div className="mt-2">
            <SearchBar
              query={browse.search.query}
              onQueryChange={browse.search.setQuery}
              isSearching={browse.search.isSearching}
            />
          </div>

          <FilterChips
            activeCategories={browse.activeCategories}
            onToggleCategory={browse.toggleCategory}
          />

          {readOnly ? (
            /* Read-only: show only download-zip batch toolbar when items selected */
            selection.selectedCount > 0 ? (
              <BatchToolbar
                selectedCount={selection.selectedCount}
                onDownloadZip={() => void browse.downloadZipSelected()}
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
                onDownloadZip={() => void browse.downloadZipSelected()}
                onDelete={handleBatchDeleteRequest}
                onClearSelection={selection.clearSelection}
              />
            ) : (
              <Toolbar
                onUploadClick={uploads.uploadFiles}
                onNewFolder={handleNewFolderRequest}
                onRequestFile={fileRequests.toggleForm}
                fileTtl={uploads.fileTtl}
                onFileTtlChange={uploads.setFileTtl}
              />
            )
          )}

          {!readOnly && fileRequests.showForm && (
            <FileRequestForm
              onSubmit={(desc) => void fileRequests.submitRequest(desc)}
              onCancel={fileRequests.toggleForm}
            />
          )}

          {!readOnly && fileRequests.requests.map((req) => (
            <FileRequestBanner
              key={req.id}
              request={req}
              isOwner={fileRequests.isMyRequest(req)}
              fulfillProgress={fileRequests.fulfillProgress.get(req.id)}
              onFulfill={(id, file) => void fileRequests.fulfillRequest(id, file)}
              onDismiss={(id) => void fileRequests.dismissRequest(id)}
              onDownload={browse.downloadPath}
            />
          ))}

          <FileList
            files={browse.sortedFiles}
            currentPath={browse.currentPath}
            onNavigate={browse.navigateTo}
            selection={{
              selectedNames: selection.selectedNames,
              isAllSelected: selection.isAllSelected,
              isIndeterminate: selection.isIndeterminate,
              toggleSelect: selection.toggleSelect,
              toggleSelectAll: selection.toggleSelectAll,
            }}
            onRename={browse.renamePath}
            onDelete={handleSingleDeleteRequest}
            onDownload={browse.downloadPath}
            onPreview={handlePreview}
            sortField={browse.sort.field}
            sortDirection={browse.sort.direction}
            onSort={browse.sort.toggleSort}
            readOnly={readOnly}
          />
        </>
      )}

      {/* Delete confirmation modal (hidden in read-only) */}
      {!readOnly && showDeleteConfirm && (
        <ConfirmDialog
          title="Confirm Delete"
          message={getDeleteMessage()}
          confirmLabel="Delete"
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
        />
      )}

      {/* Create folder dialog (hidden in read-only) */}
      {!readOnly && showCreateFolder && (
        <CreateFolderDialog
          onCreateFolder={handleCreateFolder}
          onCancel={handleCreateFolderCancel}
        />
      )}
    </>
  );
}

export default FileBrowserSection;
