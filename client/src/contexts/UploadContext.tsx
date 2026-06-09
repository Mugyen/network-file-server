import { createContext, useContext } from "react";
import type { ReactElement, ReactNode } from "react";
import { useUpload } from "../hooks/useUpload.ts";
import { useDragDrop } from "../hooks/useDragDrop.ts";
import { useBrowse } from "./BrowseContext.tsx";

/** Upload slice: the full useUpload result plus the drag-and-drop surface. */
interface UploadsContextValue extends ReturnType<typeof useUpload> {
  isDragging: boolean;
  dragHandlers: ReturnType<typeof useDragDrop>["dragHandlers"];
}

const UploadsContext = createContext<UploadsContextValue | null>(null);

interface UploadProviderProps {
  children: ReactNode;
}

/**
 * Owns the upload slice (queue, conflicts, TTL, drag-and-drop).
 * Must be nested inside a BrowseProvider: uploads target the current
 * browse path and refresh the listing on completion.
 */
export function UploadProvider({ children }: UploadProviderProps): ReactElement {
  const { currentPath, loadFiles } = useBrowse();
  const upload = useUpload(currentPath, loadFiles);
  const { isDragging, dragHandlers } = useDragDrop(upload.uploadFiles);

  const value: UploadsContextValue = { ...upload, isDragging, dragHandlers };

  return (
    <UploadsContext.Provider value={value}>{children}</UploadsContext.Provider>
  );
}

/**
 * Consumer hook for the upload slice.
 * Throws if called outside an UploadProvider (strict contract).
 */
// eslint-disable-next-line react-refresh/only-export-components -- provider and its consumer hook are intentionally co-located; fast refresh falls back to a full reload here.
export function useUploads(): UploadsContextValue {
  const value = useContext(UploadsContext);
  if (value === null) {
    throw new Error("useUploads must be used within an UploadProvider");
  }
  return value;
}
