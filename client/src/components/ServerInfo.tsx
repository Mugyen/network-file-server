import type { ServerInfo as ServerInfoData } from "../types/serverInfo.ts";
import QrCodeDisplay from "./QrCodeDisplay.tsx";

interface ServerInfoProps {
  info: ServerInfoData;
}

function ServerInfo({ info }: ServerInfoProps) {
  return (
    <div className="p-6 border rounded-lg shadow-sm max-w-md mx-auto bg-white">
      <div className="text-center mb-4">
        <p className="text-sm text-gray-500">Server URL</p>
        <a
          href={info.url}
          className="text-blue-600 hover:underline text-lg font-medium"
        >
          {info.url}
        </a>
        <p className="text-sm text-gray-400 mt-1">IP: {info.ip}</p>
      </div>
      <QrCodeDisplay svgContent={info.qr_svg} />
    </div>
  );
}

export default ServerInfo;
