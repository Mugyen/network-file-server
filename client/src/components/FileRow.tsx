import { FileType } from "../types/files.ts";
import type { FileEntry } from "../types/files.ts";

interface FileRowProps {
  file: FileEntry;
}

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function FileRow({ file }: FileRowProps) {
  const isDirectory = file.type === FileType.DIRECTORY;

  return (
    <tr className="border-b hover:bg-gray-50">
      <td className="py-2 px-3">
        <span className="mr-2" aria-hidden="true">
          {isDirectory ? "\u{1F4C1}" : "\u{1F4C4}"}
        </span>
        <span className={isDirectory ? "font-bold" : ""}>{file.name}</span>
      </td>
      <td className="py-2 px-3 text-gray-600">{file.size_display}</td>
      <td className="py-2 px-3 text-gray-600">{formatDate(file.modified)}</td>
    </tr>
  );
}

export default FileRow;
