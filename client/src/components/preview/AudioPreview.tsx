import type { FileEntry } from "../../types/files.ts";
import { Music } from "lucide-react";

interface AudioPreviewProps {
  url: string;
  file: FileEntry;
}

/**
 * HTML5 audio player with native browser controls.
 * Displays file name and size alongside the player.
 */
function AudioPreview({ url, file }: AudioPreviewProps) {
  return (
    <div className="flex flex-col items-center gap-4 py-8">
      <Music className="h-16 w-16 text-gray-400 dark:text-gray-500" />
      <p className="text-lg font-medium text-gray-800 dark:text-gray-200">
        {file.name}
      </p>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {file.size_display}
      </p>
      <audio controls src={url} className="w-full max-w-md">
        <track kind="captions" label={file.name} />
      </audio>
    </div>
  );
}

export default AudioPreview;
