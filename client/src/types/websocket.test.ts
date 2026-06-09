import { beforeEach, describe, expect, it } from "vitest";
import { getDeviceId, getDeviceName } from "./websocket.ts";

describe("getDeviceId", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("generates a UUID and persists it", () => {
    const id = getDeviceId();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
    expect(localStorage.getItem("wfs_device_id")).toBe(id);
  });

  it("returns the same ID across calls (stable identity)", () => {
    expect(getDeviceId()).toBe(getDeviceId());
  });

  it("reuses a previously persisted ID", () => {
    localStorage.setItem("wfs_device_id", "persisted-id");
    expect(getDeviceId()).toBe("persisted-id");
  });

  it("is independent of the display name", () => {
    const id = getDeviceId();
    const name = getDeviceName();
    expect(id).not.toBe(name);
    // Renaming the device must not change identity
    localStorage.setItem("wfs_device_name", "Renamed Device");
    expect(getDeviceId()).toBe(id);
  });
});

describe("getDeviceName", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("generates an adjective-animal name and persists it", () => {
    const name = getDeviceName();
    expect(name).toMatch(/^[A-Z][a-z]+ [A-Z][a-z]+$/);
    expect(localStorage.getItem("wfs_device_name")).toBe(name);
  });

  it("is stable across calls", () => {
    expect(getDeviceName()).toBe(getDeviceName());
  });
});
