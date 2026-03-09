import { useCallback, useEffect, useRef, useState } from "react";
import { WSMessageType } from "../types/websocket.ts";

/** Maximum reconnect delay in milliseconds. */
const MAX_RECONNECT_DELAY = 30000;

/** Base delay for exponential backoff in milliseconds. */
const BASE_DELAY = 1000;

/** Maximum jitter added to reconnect delay in milliseconds. */
const MAX_JITTER = 1000;

interface UseWebSocketResult {
  isConnected: boolean;
  deviceCount: number;
  sendMessage: (msg: object) => void;
  addMessageHandler: (type: string, handler: (data: unknown) => void) => void;
  removeMessageHandler: (type: string) => void;
}

/**
 * WebSocket hook with auto-reconnect via exponential backoff.
 * Stores WS in useRef (not useState) to avoid stale closure issues.
 */
export function useWebSocket(deviceName: string): UseWebSocketResult {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [deviceCount, setDeviceCount] = useState<number>(0);
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Map<string, (data: unknown) => void>>(new Map());
  const attemptRef = useRef<number>(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const mountedRef = useRef<boolean>(true);

  const connect = useCallback((): void => {
    if (!mountedRef.current) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws?device_name=${encodeURIComponent(deviceName)}`;
    const ws = new WebSocket(url);

    ws.onopen = (): void => {
      if (!mountedRef.current) return;
      setIsConnected(true);
      attemptRef.current = 0;
    };

    ws.onmessage = (event: MessageEvent): void => {
      if (!mountedRef.current) return;
      const data = JSON.parse(event.data as string) as Record<string, unknown>;
      const msgType = data.type as string;

      if (msgType === WSMessageType.DEVICE_COUNT) {
        setDeviceCount(data.count as number);
      }

      const handler = handlersRef.current.get(msgType);
      if (handler !== undefined) {
        handler(data);
      }
    };

    ws.onclose = (): void => {
      if (!mountedRef.current) return;
      setIsConnected(false);
      wsRef.current = null;

      // Exponential backoff with jitter
      const delay = Math.min(
        BASE_DELAY * Math.pow(2, attemptRef.current),
        MAX_RECONNECT_DELAY,
      );
      const jitter = Math.random() * MAX_JITTER;
      attemptRef.current += 1;

      reconnectTimerRef.current = window.setTimeout(() => {
        connect();
      }, delay + jitter);
    };

    wsRef.current = ws;
  }, [deviceName]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current !== null) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msg: object): void => {
    if (wsRef.current !== null && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const addMessageHandler = useCallback(
    (type: string, handler: (data: unknown) => void): void => {
      handlersRef.current.set(type, handler);
    },
    [],
  );

  const removeMessageHandler = useCallback((type: string): void => {
    handlersRef.current.delete(type);
  }, []);

  return { isConnected, deviceCount, sendMessage, addMessageHandler, removeMessageHandler };
}
