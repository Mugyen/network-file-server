import {
  Layers,
  Image,
  Video,
  Music,
  FileText,
  Type,
  Code,
  BookOpen,
  Archive,
  Cpu,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { FileCategory, CATEGORY_METADATA } from "../types/fileCategories.ts";

interface FilterChipsProps {
  activeCategories: Set<FileCategory>;
  onToggleCategory: (category: FileCategory) => void;
}

/** Maps CATEGORY_METADATA icon name strings to lucide-react components. */
const ICON_MAP: Record<string, LucideIcon> = {
  layers: Layers,
  image: Image,
  video: Video,
  music: Music,
  "file-text": FileText,
  type: Type,
  code: Code,
  "book-open": BookOpen,
  archive: Archive,
  cpu: Cpu,
};

/** All category keys in display order. */
const CATEGORY_ORDER: FileCategory[] = [
  FileCategory.ALL,
  FileCategory.IMAGES,
  FileCategory.VIDEO,
  FileCategory.AUDIO,
  FileCategory.DOCUMENTS,
  FileCategory.TEXT,
  FileCategory.CODE,
  FileCategory.MARKDOWN,
  FileCategory.ARCHIVES,
  FileCategory.EXECUTABLES,
];

/**
 * Horizontal row of toggleable pill/chip buttons for file type filtering.
 * "All" chip deactivates others; toggling any non-All chip deactivates "All".
 * Mobile-friendly with horizontal scroll.
 */
function FilterChips({ activeCategories, onToggleCategory }: FilterChipsProps) {
  return (
    <div className="flex flex-nowrap gap-2 overflow-x-auto hide-scrollbar py-2">
      {CATEGORY_ORDER.map((category) => {
        const meta = CATEGORY_METADATA[category];
        const isActive = activeCategories.has(category);
        const IconComponent = ICON_MAP[meta.icon];

        return (
          <button
            key={category}
            type="button"
            onClick={() => onToggleCategory(category)}
            className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-sm font-medium transition-colors ${
              isActive
                ? "bg-blue-600 text-white dark:bg-blue-500"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            }`}
          >
            {IconComponent !== undefined && (
              <IconComponent className="h-3.5 w-3.5" />
            )}
            {meta.label}
          </button>
        );
      })}
    </div>
  );
}

export default FilterChips;
