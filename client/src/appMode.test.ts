import { describe, expect, it } from "vitest";

import { AppMode, resolveAppMode } from "./appMode.ts";

describe("resolveAppMode", () => {
  it("maps each relay account path to its mode", () => {
    expect(resolveAppMode("/login")).toBe(AppMode.RelayLogin);
    expect(resolveAppMode("/signup")).toBe(AppMode.RelaySignup);
    expect(resolveAppMode("/admin")).toBe(AppMode.RelayAdmin);
    expect(resolveAppMode("/403")).toBe(AppMode.Relay403);
  });

  it("routes the LAN root to the SPA", () => {
    expect(resolveAppMode("/")).toBe(AppMode.Spa);
  });

  it("routes a relay mount path to the SPA", () => {
    expect(resolveAppMode("/m/ABC12345/")).toBe(AppMode.Spa);
    expect(resolveAppMode("/m/ABC12345/folder/sub")).toBe(AppMode.Spa);
  });

  it("does not match account pages as path prefixes", () => {
    // Only exact paths are account pages; deeper paths are the SPA.
    expect(resolveAppMode("/login/extra")).toBe(AppMode.Spa);
    expect(resolveAppMode("/admin/users")).toBe(AppMode.Spa);
  });

  it("routes unknown paths to the SPA", () => {
    expect(resolveAppMode("/some/random/path")).toBe(AppMode.Spa);
  });
});
