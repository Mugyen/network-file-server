import type { ReactElement } from "react";
import { useUploads } from "../contexts/UploadContext.tsx";
import UploadPanel from "./UploadPanel.tsx";
import ConflictDialog from "./ConflictDialog.tsx";

/**
 * Floating upload widgets: the bottom-right upload progress panel and
 * the conflict-resolution dialog. The caller gates these on read-only
 * mode, matching the pre-refactor render conditions.
 */
function UploadWidgets(): ReactElement {
  const uploads = useUploads();

  return (
    <>
      {/* Upload panel -- floating bottom-right */}
      <UploadPanel
        uploads={uploads.uploads}
        collapsed={uploads.collapsed}
        onToggleCollapse={uploads.toggleCollapsed}
        onClearCompleted={uploads.clearCompleted}
        onRetry={uploads.retryFailed}
      />

      {/* Conflict dialog for uploads */}
      {uploads.pendingConflict !== null && (
        <ConflictDialog
          fileName={uploads.pendingConflict.file.name}
          onResolve={uploads.resolveConflict}
        />
      )}
    </>
  );
}

export default UploadWidgets;
