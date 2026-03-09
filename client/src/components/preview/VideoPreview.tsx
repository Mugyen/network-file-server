import type { FileEntry } from "../../types/files.ts";

interface VideoPreviewProps {
  url: string;
  file: FileEntry;
}

/**
 * HTML5 video player with native browser controls.
 * Seeking works automatically via Range request support from the backend.
 */
function VideoPreview({ url, file }: VideoPreviewProps) {
  return (
    <div className="flex flex-col items-center">
      <video
        controls
        preload="metadata"
        src={url}
        className="max-h-[70vh] max-w-full"
      >
        <track kind="captions" label={file.name} />
      </video>
      <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{file.name}</p>
    </div>
  );
}

export default VideoPreview;
