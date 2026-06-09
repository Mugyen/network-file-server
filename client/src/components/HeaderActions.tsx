import { useState } from "react";
import type { ReactElement } from "react";
import { ClipboardList, LogOut, Monitor, Share2 } from "lucide-react";
import type { DeviceInfo } from "../types/websocket.ts";
import type { ThemeMode } from "../hooks/useTheme.ts";
import ConnectionStatus from "./ConnectionStatus.tsx";
import DevicesPanel from "./DevicesPanel.tsx";
import ShareLinksPanel from "./ShareLinksPanel.tsx";
import ThemeToggle from "./ThemeToggle.tsx";

interface HeaderActionsProps {
  isConnected: boolean;
  deviceCount: number;
  devices: DeviceInfo[];
  myDeviceId: string;
  onScratchpadToggle: () => void;
  snippetCount: number;
  themeMode: ThemeMode;
  isDark: boolean;
  onThemeToggle: () => void;
  passwordRequired: boolean;
  onLogout: () => void;
}

/**
 * The header's right-side button cluster: connection status, devices,
 * share links, scratchpad toggle, theme toggle, and logout. Owns the
 * devices and share-links panel visibility.
 */
function HeaderActions({
  isConnected,
  deviceCount,
  devices,
  myDeviceId,
  onScratchpadToggle,
  snippetCount,
  themeMode,
  isDark,
  onThemeToggle,
  passwordRequired,
  onLogout,
}: HeaderActionsProps): ReactElement {
  const [showDevices, setShowDevices] = useState<boolean>(false);
  const [showShareLinks, setShowShareLinks] = useState<boolean>(false);

  return (
    <div className="flex items-center gap-3">
      <ConnectionStatus isConnected={isConnected} deviceCount={deviceCount} />
      <button
        type="button"
        onClick={() => setShowDevices(true)}
        className="relative p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
        aria-label="Connected devices"
        title="Devices"
      >
        <Monitor className="w-5 h-5" />
        {devices.length > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[1.125rem] h-[1.125rem] flex items-center justify-center rounded-full bg-blue-500 text-white text-[10px] font-bold leading-none px-1">
            {String(devices.length)}
          </span>
        )}
      </button>
      <button
        type="button"
        onClick={() => setShowShareLinks(true)}
        className="p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
        aria-label="Share links"
        title="Share Links"
      >
        <Share2 className="w-5 h-5" />
      </button>
      <button
        type="button"
        onClick={onScratchpadToggle}
        className="relative p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
        aria-label="Toggle scratchpad"
      >
        <ClipboardList className="w-5 h-5" />
        {snippetCount > 0 && (
          <span className="absolute top-0 right-0 w-2 h-2 bg-blue-500 rounded-full" />
        )}
      </button>
      <ThemeToggle mode={themeMode} isDark={isDark} onToggle={onThemeToggle} />
      {passwordRequired && (
        <button
          type="button"
          onClick={() => {
            void import("../api/auth.ts").then((mod) => mod.logout()).then(onLogout);
          }}
          className="p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
          aria-label="Log out"
          title="Log out"
        >
          <LogOut className="w-5 h-5" />
        </button>
      )}

      {/* Devices panel */}
      <DevicesPanel
        isOpen={showDevices}
        onClose={() => setShowDevices(false)}
        devices={devices}
        myDeviceId={myDeviceId}
      />

      {/* Share links panel */}
      <ShareLinksPanel
        isOpen={showShareLinks}
        onClose={() => setShowShareLinks(false)}
      />
    </div>
  );
}

export default HeaderActions;
