import { useState, useEffect } from "react";
import { Smartphone, Laptop, Tablet, X } from "lucide-react";
import type { DeviceInfo } from "../types/websocket.ts";
import { DeviceType } from "../types/websocket.ts";

interface DevicesPanelProps {
  isOpen: boolean;
  onClose: () => void;
  devices: DeviceInfo[];
  myDeviceId: string;
}

const DEVICE_ICON_CLASS = "h-5 w-5 text-gray-500 dark:text-gray-400 flex-shrink-0";

/** Module-scope icon component so no component is created during render. */
function DeviceIcon({ deviceType }: { deviceType: DeviceType }) {
  switch (deviceType) {
    case DeviceType.PHONE:
      return <Smartphone className={DEVICE_ICON_CLASS} />;
    case DeviceType.TABLET:
      return <Tablet className={DEVICE_ICON_CLASS} />;
    case DeviceType.DESKTOP:
      return <Laptop className={DEVICE_ICON_CLASS} />;
  }
}

function formatDuration(connectedAt: string): string {
  const elapsedMs = Date.now() - new Date(connectedAt).getTime();
  const totalMinutes = Math.floor(elapsedMs / 60000);

  if (totalMinutes < 1) {
    return "just now";
  }

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) {
    return `${String(minutes)}m`;
  }
  if (minutes === 0) {
    return `${String(hours)}h`;
  }
  return `${String(hours)}h ${String(minutes)}m`;
}

function DeviceCard({ device, isMe }: { device: DeviceInfo; isMe: boolean }) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3">
      <div className="flex items-center gap-3">
        <DeviceIcon deviceType={device.device_type} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
              {device.device_name}
            </span>
            {isMe && (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                You
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {device.ip_address}
          </p>
        </div>
        <span className="text-xs text-gray-400 dark:text-gray-500 flex-shrink-0">
          {formatDuration(device.connected_at)}
        </span>
      </div>
    </div>
  );
}

function DevicesPanel({ isOpen, onClose, devices, myDeviceId }: DevicesPanelProps) {
  // Tick counter to force re-render for live duration updates
  const [, setTick] = useState<number>(0);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const interval = setInterval(() => {
      setTick((prev) => prev + 1);
    }, 30000);
    return () => clearInterval(interval);
  }, [isOpen]);

  // Sort: own device first, then by connected_at ascending
  const sortedDevices = [...devices].sort((a, b) => {
    if (a.device_id === myDeviceId) return -1;
    if (b.device_id === myDeviceId) return 1;
    return new Date(a.connected_at).getTime() - new Date(b.connected_at).getTime();
  });

  return (
    <>
      {/* Backdrop overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full sm:w-96 bg-gray-50 dark:bg-gray-900 shadow-xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
            Devices ({String(devices.length)})
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
            aria-label="Close devices panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {devices.length === 0 && (
            <p className="text-center text-gray-500 dark:text-gray-400 py-8">
              No other devices connected
            </p>
          )}

          {sortedDevices.map((device) => (
            <DeviceCard
              key={device.device_id}
              device={device}
              isMe={device.device_id === myDeviceId}
            />
          ))}
        </div>
      </div>
    </>
  );
}

export default DevicesPanel;
