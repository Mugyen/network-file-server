import { useCallback, useRef, useState } from "react";
import type { ToastMessage, WSToastPayload } from "../types/websocket.ts";
import { ToastType } from "../types/websocket.ts";

/** Maximum number of visible toasts at once. */
const MAX_VISIBLE = 3;

/** Auto-dismiss delay in milliseconds. */
const DISMISS_DELAY = 4000;

/** Monotonic counter for toast IDs (crypto.randomUUID unavailable on HTTP). */
let nextToastId = 0;

function generateToastId(): string {
  nextToastId += 1;
  return `toast-${String(Date.now())}-${String(nextToastId)}`;
}

interface UseToastResult {
  toasts: ToastMessage[];
  visibleToasts: ToastMessage[];
  overflowCount: number;
  addToast: (payload: WSToastPayload) => void;
  addErrorToast: (message: string) => void;
  dismissToast: (id: string) => void;
}

/**
 * Toast state management hook.
 * Auto-dismisses after 4s, manual dismiss via X, max 3 visible with +N overflow.
 * Stores timeout IDs in useRef to avoid memory leaks on manual dismiss.
 */
export function useToast(): UseToastResult {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const timeoutMapRef = useRef<Map<string, number>>(new Map());

  const dismissToast = useCallback((id: string): void => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timerId = timeoutMapRef.current.get(id);
    if (timerId !== undefined) {
      clearTimeout(timerId);
      timeoutMapRef.current.delete(id);
    }
  }, []);

  const addToast = useCallback(
    (payload: WSToastPayload): void => {
      const id = generateToastId();
      const toast: ToastMessage = {
        id,
        toastType: payload.toast_type,
        message: payload.message,
        deviceName: payload.device_name,
        timestamp: payload.timestamp,
      };

      setToasts((prev) => [...prev, toast]);

      const timerId = window.setTimeout(() => {
        dismissToast(id);
      }, DISMISS_DELAY);
      timeoutMapRef.current.set(id, timerId);
    },
    [dismissToast],
  );

  /** Surface a failed local operation as a toast (client-originated, not WS). */
  const addErrorToast = useCallback(
    (message: string): void => {
      addToast({
        type: "toast",
        toast_type: ToastType.ERROR,
        message,
        device_name: "",
        timestamp: new Date().toISOString(),
      });
    },
    [addToast],
  );

  const visibleToasts = toasts.slice(-MAX_VISIBLE);
  const overflowCount = Math.max(0, toasts.length - MAX_VISIBLE);

  return { toasts, visibleToasts, overflowCount, addToast, addErrorToast, dismissToast };
}
