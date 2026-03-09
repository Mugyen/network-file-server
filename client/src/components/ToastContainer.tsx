import type { ToastMessage } from "../types/websocket.ts";
import Toast from "./Toast.tsx";

interface ToastContainerProps {
  toasts: ToastMessage[];
  overflowCount: number;
  onDismiss: (id: string) => void;
}

function ToastContainer({
  toasts,
  overflowCount,
  onDismiss,
}: ToastContainerProps): React.ReactElement {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col-reverse gap-2 w-80">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
      {overflowCount > 0 && (
        <div className="text-center text-xs text-gray-500 dark:text-gray-400 py-1">
          +{overflowCount} more notification{overflowCount > 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}

export default ToastContainer;
