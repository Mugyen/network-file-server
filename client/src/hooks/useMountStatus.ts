/**
 * REST polling hook for mount connection status.
 *
 * Polls GET /m/{code}/status every 30 seconds when in remote mount mode.
 * Pauses polling when the browser tab is hidden (Page Visibility API).
 * Returns the current MountStatus enum value.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { getMountPrefix, isRemoteMount } from "../utils/remoteMount.ts";

export const MountStatus = {
  ONLINE: "online",
  OFFLINE: "offline",
  EXPIRED: "expired",
  UNKNOWN: "unknown",
} as const;

export type MountStatus = (typeof MountStatus)[keyof typeof MountStatus];

const POLL_INTERVAL_MS = 30000;

interface MountStatusResult {
  status: MountStatus;
  /** Set a callback to be invoked when status transitions to ONLINE from non-ONLINE. */
  onRecoveryRef: React.MutableRefObject<(() => void) | null>;
  /** Trigger an immediate poll (e.g. when WebSocket disconnects). */
  triggerPoll: () => void;
}

export function useMountStatus(): MountStatusResult {
  const [status, setStatus] = useState<MountStatus>(MountStatus.UNKNOWN);
  const intervalRef = useRef<number | null>(null);
  const prevStatusRef = useRef<MountStatus>(MountStatus.UNKNOWN);
  const onRecoveryRef = useRef<(() => void) | null>(null);

  const poll = useCallback(async (): Promise<void> => {
    if (!isRemoteMount()) {
      setStatus(MountStatus.ONLINE);
      return;
    }
    try {
      const resp = await fetch(`${getMountPrefix()}/status`);
      if (resp.ok) {
        const data = (await resp.json()) as { status: string };
        const newStatus = data.status as MountStatus;
        setStatus(newStatus);

        // Auto-recovery: if we transition to ONLINE from a non-ONLINE state
        if (
          newStatus === MountStatus.ONLINE &&
          prevStatusRef.current !== MountStatus.ONLINE &&
          prevStatusRef.current !== MountStatus.UNKNOWN &&
          onRecoveryRef.current !== null
        ) {
          onRecoveryRef.current();
        }
        prevStatusRef.current = newStatus;
      } else {
        setStatus(MountStatus.UNKNOWN);
      }
    } catch {
      setStatus(MountStatus.UNKNOWN);
    }
  }, []);

  useEffect(() => {
    void poll();

    function startPolling(): void {
      if (intervalRef.current === null) {
        intervalRef.current = window.setInterval(() => void poll(), POLL_INTERVAL_MS);
      }
    }

    function stopPolling(): void {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    function handleVisibilityChange(): void {
      if (document.hidden) {
        stopPolling();
      } else {
        void poll();
        startPolling();
      }
    }

    startPolling();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [poll]);

  const triggerPoll = useCallback(() => { void poll(); }, [poll]);

  return { status, onRecoveryRef, triggerPoll };
}
