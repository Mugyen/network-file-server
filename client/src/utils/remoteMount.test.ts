import { describe, it, expect, vi, beforeEach } from "vitest";

/**
 * Tests for remoteMount.ts utilities.
 *
 * MOUNT_PREFIX is computed at module load time from window.location.pathname,
 * so each test group stubs the global before importing via dynamic import.
 * vi.resetModules() ensures a fresh module evaluation per test.
 */

describe("remoteMount — LAN mode (no /m/ prefix)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("location", {
      pathname: "/",
      protocol: "http:",
      host: "192.168.1.10:8080",
    });
  });

  it("detectMountPrefix returns '' for pathname '/'", async () => {
    const { getMountPrefix } = await import("./remoteMount.ts");
    expect(getMountPrefix()).toBe("");
  });

  it("detectMountPrefix returns '' for pathname '/some/path'", async () => {
    vi.stubGlobal("location", {
      pathname: "/some/path",
      protocol: "http:",
      host: "192.168.1.10:8080",
    });
    vi.resetModules();
    const { getMountPrefix } = await import("./remoteMount.ts");
    expect(getMountPrefix()).toBe("");
  });

  it("getApiBase returns '/api' in LAN mode", async () => {
    const { getApiBase } = await import("./remoteMount.ts");
    expect(getApiBase()).toBe("/api");
  });

  it("isRemoteMount returns false in LAN mode", async () => {
    const { isRemoteMount } = await import("./remoteMount.ts");
    expect(isRemoteMount()).toBe(false);
  });

  it("getWsUrl returns ws:// URL without mount prefix in LAN mode (http)", async () => {
    const { getWsUrl } = await import("./remoteMount.ts");
    expect(getWsUrl("/ws", "device_name=test")).toBe(
      "ws://192.168.1.10:8080/ws?device_name=test",
    );
  });

  it("getWsUrl returns wss:// URL without mount prefix in LAN mode (https)", async () => {
    vi.stubGlobal("location", {
      pathname: "/",
      protocol: "https:",
      host: "192.168.1.10:8080",
    });
    vi.resetModules();
    const { getWsUrl } = await import("./remoteMount.ts");
    expect(getWsUrl("/ws", "device_name=test")).toBe(
      "wss://192.168.1.10:8080/ws?device_name=test",
    );
  });
});

describe("remoteMount — Remote mode (/m/ABC12345 prefix)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("location", {
      pathname: "/m/ABC12345/",
      protocol: "https:",
      host: "relay.example.com",
    });
  });

  it("detectMountPrefix returns '/m/ABC12345' for pathname '/m/ABC12345/'", async () => {
    const { getMountPrefix } = await import("./remoteMount.ts");
    expect(getMountPrefix()).toBe("/m/ABC12345");
  });

  it("detectMountPrefix returns '/m/ABC12345' for pathname '/m/ABC12345/api/files'", async () => {
    vi.stubGlobal("location", {
      pathname: "/m/ABC12345/api/files",
      protocol: "https:",
      host: "relay.example.com",
    });
    vi.resetModules();
    const { getMountPrefix } = await import("./remoteMount.ts");
    expect(getMountPrefix()).toBe("/m/ABC12345");
  });

  it("getApiBase returns '/m/ABC12345/api' in remote mode", async () => {
    const { getApiBase } = await import("./remoteMount.ts");
    expect(getApiBase()).toBe("/m/ABC12345/api");
  });

  it("isRemoteMount returns true in remote mode", async () => {
    const { isRemoteMount } = await import("./remoteMount.ts");
    expect(isRemoteMount()).toBe(true);
  });

  it("getWsUrl returns wss:// URL with mount prefix in remote mode", async () => {
    const { getWsUrl } = await import("./remoteMount.ts");
    expect(getWsUrl("/ws", "device_name=test")).toBe(
      "wss://relay.example.com/m/ABC12345/ws?device_name=test",
    );
  });
});
