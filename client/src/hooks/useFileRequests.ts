import { useCallback, useEffect, useRef, useState } from "react";
import type { FileRequest } from "../types/fileRequests.ts";
import { RequestStatus } from "../types/fileRequests.ts";
import { WSMessageType } from "../types/websocket.ts";
import {
  isFileRequestPayload,
  isRequestDismissedPayload,
} from "../utils/wsGuards.ts";
import {
  fetchFileRequests,
  createFileRequest,
  fulfillFileRequest,
  dismissFileRequest,
} from "../api/fileRequests.ts";

interface UseFileRequestsResult {
  requests: FileRequest[];
  showForm: boolean;
  fulfillProgress: Map<string, number>;
  toggleForm: () => void;
  submitRequest: (description: string) => Promise<void>;
  fulfillRequest: (requestId: string, file: File) => Promise<void>;
  dismissRequest: (requestId: string) => Promise<void>;
  isMyRequest: (request: FileRequest) => boolean;
}

/**
 * Hook for managing file requests with WebSocket real-time sync.
 * Identity (ownership, dismissal rights) is keyed on the stable deviceId;
 * deviceName is presentational only.
 */
export function useFileRequests(
  addMessageHandler: (type: string, handler: (data: unknown) => void) => void,
  removeMessageHandler: (type: string) => void,
  deviceId: string,
  deviceName: string,
  onFileUploaded: () => void,
): UseFileRequestsResult {
  const [requests, setRequests] = useState<FileRequest[]>([]);
  const [showForm, setShowForm] = useState<boolean>(false);
  const [fulfillProgress, setFulfillProgress] = useState<Map<string, number>>(
    () => new Map(),
  );
  const deviceIdRef = useRef<string>(deviceId);
  deviceIdRef.current = deviceId;
  const deviceNameRef = useRef<string>(deviceName);
  deviceNameRef.current = deviceName;

  // Load requests on mount
  useEffect(() => {
    async function load(): Promise<void> {
      try {
        const data = await fetchFileRequests();
        setRequests(data);
      } catch (err: unknown) {
        // Background load — requests will sync via WS, but log the failure.
        console.error("Failed to load file requests:", err);
      }
    }
    void load();
  }, []);

  // Register WS handlers
  useEffect(() => {
    addMessageHandler(WSMessageType.REQUEST_CREATED, (data: unknown) => {
      if (!isFileRequestPayload(data)) {
        console.error("Malformed WS message", WSMessageType.REQUEST_CREATED, data);
        return;
      }
      const msg = data;
      setRequests((prev) => [msg.request, ...prev]);
    });

    addMessageHandler(WSMessageType.REQUEST_FULFILLED, (data: unknown) => {
      if (!isFileRequestPayload(data)) {
        console.error("Malformed WS message", WSMessageType.REQUEST_FULFILLED, data);
        return;
      }
      const msg = data;
      setRequests((prev) =>
        prev.map((r) => (r.id === msg.request.id ? msg.request : r)),
      );
    });

    addMessageHandler(WSMessageType.REQUEST_DISMISSED, (data: unknown) => {
      if (!isRequestDismissedPayload(data)) {
        console.error("Malformed WS message", WSMessageType.REQUEST_DISMISSED, data);
        return;
      }
      const msg = data;
      setRequests((prev) => prev.filter((r) => r.id !== msg.request_id));
    });

    return () => {
      removeMessageHandler(WSMessageType.REQUEST_CREATED);
      removeMessageHandler(WSMessageType.REQUEST_FULFILLED);
      removeMessageHandler(WSMessageType.REQUEST_DISMISSED);
    };
  }, [addMessageHandler, removeMessageHandler]);

  const toggleForm = useCallback((): void => {
    setShowForm((prev) => !prev);
  }, []);

  const submitRequest = useCallback(
    async (description: string): Promise<void> => {
      const request = await createFileRequest(
        description,
        deviceIdRef.current,
        deviceNameRef.current,
      );
      setRequests((prev) => [request, ...prev]);
      setShowForm(false);
    },
    [],
  );

  const fulfillRequest = useCallback(
    async (requestId: string, file: File): Promise<void> => {
      const name = deviceNameRef.current;
      setFulfillProgress((prev) => {
        const next = new Map(prev);
        next.set(requestId, 0);
        return next;
      });

      try {
        const fulfilled = await fulfillFileRequest(
          requestId,
          file,
          name,
          (percent: number) => {
            setFulfillProgress((prev) => {
              const next = new Map(prev);
              next.set(requestId, percent);
              return next;
            });
          },
        );
        setRequests((prev) =>
          prev.map((r) => (r.id === requestId ? fulfilled : r)),
        );
        onFileUploaded();
      } finally {
        setFulfillProgress((prev) => {
          const next = new Map(prev);
          next.delete(requestId);
          return next;
        });
      }
    },
    [onFileUploaded],
  );

  const dismissRequest = useCallback(
    async (requestId: string): Promise<void> => {
      await dismissFileRequest(requestId, deviceIdRef.current);
      setRequests((prev) => prev.filter((r) => r.id !== requestId));
    },
    [],
  );

  const isMyRequest = useCallback(
    (request: FileRequest): boolean => {
      return request.requester_device_id === deviceIdRef.current;
    },
    [],
  );

  return {
    requests: requests.filter((r) => r.status !== RequestStatus.DISMISSED),
    showForm,
    fulfillProgress,
    toggleForm,
    submitRequest,
    fulfillRequest,
    dismissRequest,
    isMyRequest,
  };
}
