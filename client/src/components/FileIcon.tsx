import {
  File,
  Folder,
  FileText,
  FileImage,
  FileCode,
  FileMusic,
  FileArchive,
  FileVideo,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

/**
 * Maps ~30 common file extensions to lucide-react icon components.
 * Unknown extensions fall back to the generic File icon.
 */
const EXTENSION_ICON_MAP: Record<string, LucideIcon> = {
  // Images
  jpg: FileImage,
  jpeg: FileImage,
  png: FileImage,
  gif: FileImage,
  svg: FileImage,
  webp: FileImage,
  bmp: FileImage,
  ico: FileImage,
  // Video
  mp4: FileVideo,
  mov: FileVideo,
  avi: FileVideo,
  mkv: FileVideo,
  webm: FileVideo,
  wmv: FileVideo,
  // Audio
  mp3: FileMusic,
  wav: FileMusic,
  flac: FileMusic,
  aac: FileMusic,
  ogg: FileMusic,
  m4a: FileMusic,
  // Code
  js: FileCode,
  ts: FileCode,
  py: FileCode,
  rs: FileCode,
  go: FileCode,
  jsx: FileCode,
  tsx: FileCode,
  html: FileCode,
  css: FileCode,
  json: FileCode,
  xml: FileCode,
  yaml: FileCode,
  yml: FileCode,
  // Text / Documents
  txt: FileText,
  md: FileText,
  pdf: FileText,
  doc: FileText,
  docx: FileText,
  rtf: FileText,
  csv: FileText,
  // Archives
  zip: FileArchive,
  tar: FileArchive,
  gz: FileArchive,
  rar: FileArchive,
  "7z": FileArchive,
  bz2: FileArchive,
};

function getIconForFile(fileName: string): LucideIcon {
  const dotIndex = fileName.lastIndexOf(".");
  if (dotIndex === -1) {
    return File;
  }
  const ext = fileName.slice(dotIndex + 1).toLowerCase();
  return EXTENSION_ICON_MAP[ext] ?? File;
}

interface FileIconProps {
  fileName: string;
  isDirectory: boolean;
}

/**
 * Renders a lucide-react icon matching the file type.
 * Directories get a blue folder icon; files get a gray icon based on extension.
 */
function FileIcon({ fileName, isDirectory }: FileIconProps) {
  if (isDirectory) {
    return <Folder size={18} className="text-blue-500" />;
  }
  const IconComponent = getIconForFile(fileName);
  return <IconComponent size={18} className="text-gray-500" />;
}

export default FileIcon;
