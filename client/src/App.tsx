import { useEffect, useState } from "react";
import type { FileEntry } from "./types/files.ts";
import type { ServerInfo as ServerInfoData } from "./types/serverInfo.ts";
import { fetchFiles } from "./api/files.ts";
import { fetchServerInfo } from "./api/serverInfo.ts";
import FileList from "./components/FileList.tsx";
import ServerInfoComponent from "./components/ServerInfo.tsx";

function App() {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [serverInfo, setServerInfo] = useState<ServerInfoData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData(): Promise<void> {
      try {
        const [listing, info] = await Promise.all([
          fetchFiles(""),
          fetchServerInfo(),
        ]);
        setFiles(listing.entries);
        setServerInfo(info);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load data";
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    void loadData();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="py-6">
        <h1 className="text-2xl font-bold text-center text-gray-800">
          WiFi File Server
        </h1>
      </header>

      <main className="container mx-auto p-4 max-w-4xl">
        {loading && (
          <p className="text-center text-gray-500 py-8">Loading...</p>
        )}

        {error !== null && (
          <p className="text-center text-red-600 py-4">{error}</p>
        )}

        {!loading && serverInfo !== null && (
          <div className="mb-8">
            <ServerInfoComponent info={serverInfo} />
          </div>
        )}

        {!loading && <FileList files={files} />}
      </main>
    </div>
  );
}

export default App;
