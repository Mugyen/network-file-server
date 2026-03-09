import type { FileEntry } from "../../types/files.ts";

interface PdfPreviewProps {
  url: string;
  file: FileEntry;
}

/**
 * PDF preview using browser's native PDF renderer via iframe.
 * The browser provides zoom, scroll, and page navigation controls.
 */
function PdfPreview({ url, file }: PdfPreviewProps) {
  return (
    <div className="bg-gray-100 dark:bg-gray-200 rounded">
      <iframe
        src={url}
        title={file.name}
        className="w-full h-[75vh] rounded"
      />
    </div>
  );
}

export default PdfPreview;
