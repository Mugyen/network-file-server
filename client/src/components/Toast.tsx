import { Upload, Wifi, WifiOff, Bell, X } from "lucide-react";
import type { ToastMessage } from "../types/websocket.ts";
import { ToastType } from "../types/websocket.ts";

interface ToastProps {
  toast: ToastMessage;
  onDismiss: (id: string) => void;
}

function getToastIcon(toastType: ToastType): React.ReactNode {
  switch (toastType) {
    case ToastType.FILE_UPLOADED:
      return <Upload className="w-4 h-4 text-blue-500" />;
    case ToastType.DEVICE_CONNECTED:
      return <Wifi className="w-4 h-4 text-green-500" />;
    case ToastType.DEVICE_DISCONNECTED:
      return <WifiOff className="w-4 h-4 text-red-500" />;
    case ToastType.REQUEST_CREATED:
    case ToastType.REQUEST_FULFILLED:
      return <Bell className="w-4 h-4 text-yellow-500" />;
    default:
      return <Bell className="w-4 h-4 text-gray-500" />;
  }
}

function Toast({ toast, onDismiss }: ToastProps): React.ReactElement {
  return (
    <div className="bg-white dark:bg-gray-800 shadow-lg rounded-lg p-3 border border-gray-200 dark:border-gray-700 flex items-start gap-2 animate-[slideInRight_0.3s_ease-out]">
      <div className="flex-shrink-0 mt-0.5">{getToastIcon(toast.toastType)}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-800 dark:text-gray-200 truncate">
          {toast.message}
        </p>
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        aria-label="Dismiss notification"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export default Toast;
