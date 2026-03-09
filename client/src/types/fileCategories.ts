/**
 * File category type system.
 *
 * Shared contract between FilterChips, PreviewModal, and FileIcon.
 * Maps file extensions to categories for filtering, preview detection,
 * and UI metadata.
 */

/** File category discriminator for filtering and preview logic. */
export const FileCategory = {
  ALL: "all",
  IMAGES: "images",
  VIDEO: "video",
  AUDIO: "audio",
  DOCUMENTS: "documents",
  TEXT: "text",
  CODE: "code",
  MARKDOWN: "markdown",
  ARCHIVES: "archives",
  EXECUTABLES: "executables",
} as const;

export type FileCategory = (typeof FileCategory)[keyof typeof FileCategory];

/** Maps every known file extension to its category. */
export const EXTENSION_CATEGORY_MAP: Record<string, FileCategory> = {
  // Images
  jpg: FileCategory.IMAGES,
  jpeg: FileCategory.IMAGES,
  png: FileCategory.IMAGES,
  gif: FileCategory.IMAGES,
  svg: FileCategory.IMAGES,
  webp: FileCategory.IMAGES,
  bmp: FileCategory.IMAGES,
  ico: FileCategory.IMAGES,
  tiff: FileCategory.IMAGES,

  // Video
  mp4: FileCategory.VIDEO,
  webm: FileCategory.VIDEO,
  mov: FileCategory.VIDEO,
  avi: FileCategory.VIDEO,
  mkv: FileCategory.VIDEO,
  flv: FileCategory.VIDEO,
  wmv: FileCategory.VIDEO,

  // Audio
  mp3: FileCategory.AUDIO,
  wav: FileCategory.AUDIO,
  ogg: FileCategory.AUDIO,
  flac: FileCategory.AUDIO,
  aac: FileCategory.AUDIO,
  m4a: FileCategory.AUDIO,
  wma: FileCategory.AUDIO,

  // Documents
  pdf: FileCategory.DOCUMENTS,
  doc: FileCategory.DOCUMENTS,
  docx: FileCategory.DOCUMENTS,
  xls: FileCategory.DOCUMENTS,
  xlsx: FileCategory.DOCUMENTS,
  ppt: FileCategory.DOCUMENTS,
  pptx: FileCategory.DOCUMENTS,
  odt: FileCategory.DOCUMENTS,
  ods: FileCategory.DOCUMENTS,
  odp: FileCategory.DOCUMENTS,

  // Text
  txt: FileCategory.TEXT,
  csv: FileCategory.TEXT,
  log: FileCategory.TEXT,
  ini: FileCategory.TEXT,
  cfg: FileCategory.TEXT,
  conf: FileCategory.TEXT,
  env: FileCategory.TEXT,

  // Code
  js: FileCategory.CODE,
  ts: FileCategory.CODE,
  jsx: FileCategory.CODE,
  tsx: FileCategory.CODE,
  py: FileCategory.CODE,
  go: FileCategory.CODE,
  rs: FileCategory.CODE,
  java: FileCategory.CODE,
  c: FileCategory.CODE,
  cpp: FileCategory.CODE,
  h: FileCategory.CODE,
  hpp: FileCategory.CODE,
  rb: FileCategory.CODE,
  php: FileCategory.CODE,
  swift: FileCategory.CODE,
  kt: FileCategory.CODE,
  scala: FileCategory.CODE,
  sh: FileCategory.CODE,
  bash: FileCategory.CODE,
  zsh: FileCategory.CODE,
  sql: FileCategory.CODE,
  html: FileCategory.CODE,
  css: FileCategory.CODE,
  scss: FileCategory.CODE,
  yaml: FileCategory.CODE,
  yml: FileCategory.CODE,
  json: FileCategory.CODE,
  xml: FileCategory.CODE,
  toml: FileCategory.CODE,

  // Markdown
  md: FileCategory.MARKDOWN,
  mdx: FileCategory.MARKDOWN,

  // Archives
  zip: FileCategory.ARCHIVES,
  tar: FileCategory.ARCHIVES,
  gz: FileCategory.ARCHIVES,
  bz2: FileCategory.ARCHIVES,
  xz: FileCategory.ARCHIVES,
  rar: FileCategory.ARCHIVES,
  "7z": FileCategory.ARCHIVES,
  tgz: FileCategory.ARCHIVES,

  // Executables
  exe: FileCategory.EXECUTABLES,
  msi: FileCategory.EXECUTABLES,
  dmg: FileCategory.EXECUTABLES,
  app: FileCategory.EXECUTABLES,
  bin: FileCategory.EXECUTABLES,
  deb: FileCategory.EXECUTABLES,
  rpm: FileCategory.EXECUTABLES,
  apk: FileCategory.EXECUTABLES,
  elf: FileCategory.EXECUTABLES,
  out: FileCategory.EXECUTABLES,
};

/** Categories that support inline preview. */
const PREVIEWABLE_CATEGORIES: ReadonlySet<FileCategory> = new Set([
  FileCategory.IMAGES,
  FileCategory.VIDEO,
  FileCategory.AUDIO,
  FileCategory.DOCUMENTS,
  FileCategory.TEXT,
  FileCategory.CODE,
  FileCategory.MARKDOWN,
]);

/**
 * Get the file category for a given file name.
 *
 * Extracts the extension and looks it up in EXTENSION_CATEGORY_MAP.
 * Returns FileCategory.ALL if the extension is not recognized.
 * Throws Error if fileName is empty.
 */
export function getFileCategory(fileName: string): FileCategory {
  if (fileName === "") {
    throw new Error("fileName must not be empty");
  }

  const dotIndex = fileName.lastIndexOf(".");
  if (dotIndex === -1 || dotIndex === fileName.length - 1) {
    return FileCategory.ALL;
  }

  const extension = fileName.slice(dotIndex + 1).toLowerCase();
  const category = EXTENSION_CATEGORY_MAP[extension];
  if (category === undefined) {
    return FileCategory.ALL;
  }
  return category;
}

/**
 * Check if a file is previewable based on its category.
 *
 * Returns true for images, video, audio, documents, text, code, markdown.
 * Returns false for archives, executables, and unrecognized extensions.
 * Throws Error if fileName is empty.
 */
export function isPreviewable(fileName: string): boolean {
  if (fileName === "") {
    throw new Error("fileName must not be empty");
  }

  const category = getFileCategory(fileName);
  return PREVIEWABLE_CATEGORIES.has(category);
}

/**
 * Get all file extensions belonging to a given category.
 *
 * Returns an empty array for FileCategory.ALL since it represents
 * unrecognized extensions.
 */
export function getCategoryExtensions(category: FileCategory): string[] {
  if (category === FileCategory.ALL) {
    return [];
  }

  const extensions: string[] = [];
  for (const [ext, cat] of Object.entries(EXTENSION_CATEGORY_MAP)) {
    if (cat === category) {
      extensions.push(ext);
    }
  }
  return extensions;
}

/** Display metadata for each file category. */
export const CATEGORY_METADATA: Record<
  FileCategory,
  { label: string; icon: string }
> = {
  [FileCategory.ALL]: { label: "All", icon: "layers" },
  [FileCategory.IMAGES]: { label: "Images", icon: "image" },
  [FileCategory.VIDEO]: { label: "Video", icon: "video" },
  [FileCategory.AUDIO]: { label: "Audio", icon: "music" },
  [FileCategory.DOCUMENTS]: { label: "Documents", icon: "file-text" },
  [FileCategory.TEXT]: { label: "Text", icon: "type" },
  [FileCategory.CODE]: { label: "Code", icon: "code" },
  [FileCategory.MARKDOWN]: { label: "Markdown", icon: "book-open" },
  [FileCategory.ARCHIVES]: { label: "Archives", icon: "archive" },
  [FileCategory.EXECUTABLES]: { label: "Executables", icon: "cpu" },
};
