import { describe, expect, it } from "vitest";
import {
  isDeviceCountPayload,
  isDeviceInfo,
  isDeviceListPayload,
  isFileRequest,
  isFileRequestPayload,
  isRecord,
  isRequestDismissedPayload,
  isSnippet,
  isSnippetDeletedPayload,
  isSnippetPayload,
  isToastPayload,
} from "./wsGuards.ts";
import type { DeviceInfo } from "../types/websocket.ts";
import type { FileRequest } from "../types/fileRequests.ts";
import type { Snippet } from "../types/clipboard.ts";

const validDevice: DeviceInfo = {
  device_id: "dev-1",
  device_name: "Swift Fox",
  ip_address: "192.168.1.2",
  device_type: "phone",
  connected_at: "2026-06-10T00:00:00Z",
};

const validSnippet: Snippet = {
  id: "snip-1",
  title: "Untitled",
  content: "hello",
  created_at: "2026-06-10T00:00:00Z",
  updated_at: "2026-06-10T00:00:01Z",
};

const validRequest: FileRequest = {
  id: "req-1",
  description: "tax PDF",
  requester_device_id: "dev-1",
  requester_device_name: "Swift Fox",
  status: "pending",
  created_at: "2026-06-10T00:00:00Z",
  fulfilled_by_device_name: null,
  fulfilled_file_name: null,
  fulfilled_file_path: null,
  fulfilled_at: null,
};

/** Non-object junk every guard must reject. */
const JUNK: unknown[] = [null, undefined, 42, "string", true, [1, 2]];

/** Shallow copy without `key` (loosely typed on purpose: guards take unknown). */
function omit<T extends object>(obj: T, key: keyof T): Record<string, unknown> {
  return Object.fromEntries(Object.entries(obj).filter(([k]) => k !== key));
}

describe("isRecord", () => {
  it("accepts plain objects", () => {
    expect(isRecord({})).toBe(true);
    expect(isRecord({ a: 1 })).toBe(true);
  });

  it("rejects null, arrays, and primitives", () => {
    for (const junk of JUNK) {
      expect(isRecord(junk)).toBe(false);
    }
  });
});

describe("isDeviceInfo", () => {
  it("accepts a valid device", () => {
    expect(isDeviceInfo(validDevice)).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isDeviceInfo(junk)).toBe(false);
    }
  });

  it("rejects a missing field", () => {
    expect(isDeviceInfo(omit(validDevice, "device_id"))).toBe(false);
  });

  it("rejects a wrong-typed field", () => {
    expect(isDeviceInfo({ ...validDevice, ip_address: 127 })).toBe(false);
  });

  it("rejects an unknown device_type", () => {
    expect(isDeviceInfo({ ...validDevice, device_type: "toaster" })).toBe(false);
  });
});

describe("isDeviceListPayload", () => {
  const valid = {
    type: "device_list",
    devices: [validDevice],
    your_device_id: "dev-1",
  };

  it("accepts a valid payload (including an empty device list)", () => {
    expect(isDeviceListPayload(valid)).toBe(true);
    expect(isDeviceListPayload({ ...valid, devices: [] })).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isDeviceListPayload(junk)).toBe(false);
    }
  });

  it("rejects a wrong type tag", () => {
    expect(isDeviceListPayload({ ...valid, type: "device_count" })).toBe(false);
  });

  it("rejects a non-array devices field", () => {
    expect(isDeviceListPayload({ ...valid, devices: "none" })).toBe(false);
  });

  it("rejects a list containing a malformed device", () => {
    expect(
      isDeviceListPayload({ ...valid, devices: [validDevice, { device_id: 1 }] }),
    ).toBe(false);
  });

  it("rejects a missing your_device_id", () => {
    expect(isDeviceListPayload({ type: "device_list", devices: [] })).toBe(false);
  });
});

describe("isDeviceCountPayload", () => {
  it("accepts a valid payload", () => {
    expect(isDeviceCountPayload({ type: "device_count", count: 3 })).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isDeviceCountPayload(junk)).toBe(false);
    }
  });

  it("rejects a missing count", () => {
    expect(isDeviceCountPayload({ type: "device_count" })).toBe(false);
  });

  it("rejects a non-numeric or non-finite count", () => {
    expect(isDeviceCountPayload({ type: "device_count", count: "3" })).toBe(false);
    expect(isDeviceCountPayload({ type: "device_count", count: NaN })).toBe(false);
  });

  it("rejects a wrong type tag", () => {
    expect(isDeviceCountPayload({ type: "toast", count: 3 })).toBe(false);
  });
});

describe("isToastPayload", () => {
  const valid = {
    type: "toast",
    toast_type: "device_connected",
    message: "Swift Fox connected",
    device_name: "Swift Fox",
    timestamp: "2026-06-10T00:00:00Z",
  };

  it("accepts a valid payload", () => {
    expect(isToastPayload(valid)).toBe(true);
  });

  it("accepts a payload with extra fields (device_info)", () => {
    expect(isToastPayload({ ...valid, device_info: validDevice })).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isToastPayload(junk)).toBe(false);
    }
  });

  it("rejects an unknown toast_type", () => {
    expect(isToastPayload({ ...valid, toast_type: "explosion" })).toBe(false);
  });

  it("rejects a missing message", () => {
    expect(isToastPayload(omit(valid, "message"))).toBe(false);
  });

  it("rejects a wrong-typed timestamp", () => {
    expect(isToastPayload({ ...valid, timestamp: 1718000000 })).toBe(false);
  });
});

describe("isSnippet", () => {
  it("accepts a valid snippet", () => {
    expect(isSnippet(validSnippet)).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isSnippet(junk)).toBe(false);
    }
  });

  it("rejects a missing field", () => {
    expect(isSnippet(omit(validSnippet, "content"))).toBe(false);
  });

  it("rejects a wrong-typed field", () => {
    expect(isSnippet({ ...validSnippet, id: 7 })).toBe(false);
  });
});

describe("isSnippetPayload", () => {
  it("accepts a valid payload", () => {
    expect(isSnippetPayload({ snippet: validSnippet })).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isSnippetPayload(junk)).toBe(false);
    }
  });

  it("rejects a missing snippet field", () => {
    expect(isSnippetPayload({})).toBe(false);
  });

  it("rejects a malformed nested snippet", () => {
    expect(isSnippetPayload({ snippet: { id: "x" } })).toBe(false);
    expect(isSnippetPayload({ snippet: null })).toBe(false);
  });
});

describe("isSnippetDeletedPayload", () => {
  it("accepts a valid payload", () => {
    expect(isSnippetDeletedPayload({ snippet_id: "snip-1" })).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isSnippetDeletedPayload(junk)).toBe(false);
    }
  });

  it("rejects a missing or wrong-typed snippet_id", () => {
    expect(isSnippetDeletedPayload({})).toBe(false);
    expect(isSnippetDeletedPayload({ snippet_id: 9 })).toBe(false);
  });
});

describe("isFileRequest", () => {
  it("accepts a pending request with null fulfilled fields", () => {
    expect(isFileRequest(validRequest)).toBe(true);
  });

  it("accepts a fulfilled request with string fulfilled fields", () => {
    expect(
      isFileRequest({
        ...validRequest,
        status: "fulfilled",
        fulfilled_by_device_name: "Brave Owl",
        fulfilled_file_name: "taxes.pdf",
        fulfilled_file_path: "taxes.pdf",
        fulfilled_at: "2026-06-10T01:00:00Z",
      }),
    ).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isFileRequest(junk)).toBe(false);
    }
  });

  it("rejects an unknown status", () => {
    expect(isFileRequest({ ...validRequest, status: "vaporized" })).toBe(false);
  });

  it("rejects a missing field", () => {
    expect(isFileRequest(omit(validRequest, "description"))).toBe(false);
  });

  it("rejects undefined fulfilled fields (must be string or null)", () => {
    expect(isFileRequest(omit(validRequest, "fulfilled_at"))).toBe(false);
  });
});

describe("isFileRequestPayload", () => {
  it("accepts a valid payload", () => {
    expect(isFileRequestPayload({ request: validRequest })).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isFileRequestPayload(junk)).toBe(false);
    }
  });

  it("rejects a missing or malformed nested request", () => {
    expect(isFileRequestPayload({})).toBe(false);
    expect(isFileRequestPayload({ request: { id: "req-1" } })).toBe(false);
  });
});

describe("isRequestDismissedPayload", () => {
  it("accepts a valid payload", () => {
    expect(isRequestDismissedPayload({ request_id: "req-1" })).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const junk of JUNK) {
      expect(isRequestDismissedPayload(junk)).toBe(false);
    }
  });

  it("rejects a missing or wrong-typed request_id", () => {
    expect(isRequestDismissedPayload({})).toBe(false);
    expect(isRequestDismissedPayload({ request_id: 4 })).toBe(false);
  });
});
