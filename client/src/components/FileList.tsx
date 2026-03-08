import type { FileEntry } from "../types/files.ts";
import FileRow from "./FileRow.tsx";

interface FileListProps {
  files: FileEntry[];
}

function FileList({ files }: FileListProps) {
  if (files.length === 0) {
    return (
      <p className="text-center text-gray-500 py-8">
        No files in this directory
      </p>
    );
  }

  return (
    <table className="w-full text-left">
      <thead>
        <tr className="border-b border-gray-300">
          <th className="py-2 px-3 font-semibold">Name</th>
          <th className="py-2 px-3 font-semibold">Size</th>
          <th className="py-2 px-3 font-semibold">Modified</th>
        </tr>
      </thead>
      <tbody>
        {files.map((file) => (
          <FileRow key={file.name} file={file} />
        ))}
      </tbody>
    </table>
  );
}

export default FileList;
