import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the relay auth feature.
 *
 * The live stack (relay + open/restricted mounts) is brought up by
 * scripts/e2e.sh, which exports E2E_BASE_URL / E2E_OPEN_CODE /
 * E2E_RESTRICTED_CODE. Tests are serialized (workers: 1): the restricted
 * flow mutates shared relay state (access requests, allowlist).
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8001";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
