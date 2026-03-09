import { useState } from "react";
import { Loader2 } from "lucide-react";

interface ConnectionStatusProps {
  isConnected: boolean;
  deviceCount: number;
}

function ConnectionStatus({
  isConnected,
  deviceCount,
}: ConnectionStatusProps): React.ReactElement {
  const [showTooltip, setShowTooltip] = useState<boolean>(false);

  return (
    <>
      <div
        className="relative flex items-center"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <div
          className={`w-2.5 h-2.5 rounded-full ${
            isConnected ? "bg-green-500" : "bg-red-500"
          }`}
        />
        {showTooltip && (
          <div className="absolute top-full right-0 mt-1 px-2 py-1 bg-gray-800 dark:bg-gray-700 text-white text-xs rounded whitespace-nowrap z-50">
            {isConnected
              ? `${String(deviceCount)} device${deviceCount !== 1 ? "s" : ""} connected`
              : "Disconnected"}
          </div>
        )}
      </div>
    </>
  );
}

export function ReconnectingBanner(): React.ReactElement {
  return (
    <div className="bg-yellow-50 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 text-sm text-center py-1 flex items-center justify-center gap-2">
      <Loader2 className="w-4 h-4 animate-spin" />
      Reconnecting...
    </div>
  );
}

export default ConnectionStatus;
