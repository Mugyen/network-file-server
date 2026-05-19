import { useCallback, useEffect, useRef, useState } from "react";
import { WSMessageType } from "../types/websocket.ts";
import type { DeviceInfo } from "../types/websocket.ts";
import { getWsUrl } from "../utils/remoteMount.ts";

/** Maximum reconnect delay in milliseconds. */
const MAX_RECONNECT_DELAY = 30000;

/** Base delay for exponential backoff in milliseconds. */
const BASE_DELAY = 1000;

/** Maximum jitter added to reconnect delay in milliseconds. */
const MAX_JITTER = 1000;

/**
 * Minimum time a connection must stay open before it counts as "stable"
 * and the backoff attempt counter is reset. The relay accepts the WS
 * upgrade before it knows whether the agent is reachable, so a dead mount
 * still produces a brief onopen→onclose. Without this gate the counter
 * resets every attempt and reconnects hammer the relay every ~1s forever.
 */
const STABLE_CONNECTION_MS = 3000;

interface UseWebSocketResult {
  isConnected: boolean;
  deviceCount: number;
  devices: DeviceInfo[];
  myDeviceId: string;
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
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [myDeviceId, setMyDeviceId] = useState<string>("");
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Map<string, (data: unknown) => void>>(new Map());
  const attemptRef = useRef<number>(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const stableTimerRef = useRef<number | null>(null);
  const mountedRef = useRef<boolean>(true);

  const connect = useCallback((): void => {
    if (!mountedRef.current) return;

    const url = getWsUrl("/ws", `device_name=${encodeURIComponent(deviceName)}`);
    const ws = new WebSocket(url);

    ws.onopen = (): void => {
      if (!mountedRef.current) return;
      setIsConnected(true);
      // Only reset backoff if the connection survives long enough to be
      // considered real. A relay that immediately closes (dead mount)
      // never reaches this timer, so the counter keeps escalating.
      stableTimerRef.current = window.setTimeout(() => {
        attemptRef.current = 0;
        stableTimerRef.current = null;
      }, STABLE_CONNECTION_MS);
    };

    ws.onmessage = (event: MessageEvent): void => {
      if (!mountedRef.current) return;
      const data = JSON.parse(event.data as string) as Record<string, unknown>;
      const msgType = data.type as string;

      if (msgType === WSMessageType.DEVICE_COUNT) {
        setDeviceCount(data.count as number);
      }

      if (msgType === WSMessageType.DEVICE_LIST) {
        setDevices(data.devices as DeviceInfo[]);
        setMyDeviceId(data.your_device_id as string);
      }

      if (msgType === WSMessageType.TOAST) {
        const toastType = data.toast_type as string;
        if (toastType === "device_connected" && data.device_info !== undefined) {
          const newDevice = data.device_info as DeviceInfo;
          setDevices((prev) => {
            // Avoid duplicates
            if (prev.some((d) => d.device_id === newDevice.device_id)) {
              return prev;
            }
            return [...prev, newDevice];
          });
        }
        if (toastType === "device_disconnected" && data.device_id !== undefined) {
          const disconnectedId = data.device_id as string;
          setDevices((prev) => prev.filter((d) => d.device_id !== disconnectedId));
        }
      }

      const handler = handlersRef.current.get(msgType);
      if (handler !== undefined) {
        handler(data);
      }
    };

    ws.onclose = (): void => {
      if (!mountedRef.current) return;
      setIsConnected(false);
      setDevices([]);
      setMyDeviceId("");
      wsRef.current = null;

      // Connection didn't survive to "stable" — cancel the pending reset
      // so this failed attempt still counts toward the backoff.
      if (stableTimerRef.current !== null) {
        clearTimeout(stableTimerRef.current);
        stableTimerRef.current = null;
      }

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
      if (stableTimerRef.current !== null) {
        clearTimeout(stableTimerRef.current);
        stableTimerRef.current = null;
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

  return { isConnected, deviceCount, devices, myDeviceId, sendMessage, addMessageHandler, removeMessageHandler };
}
