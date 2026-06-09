import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: false,
    // Playwright specs live in e2e/ and are run by `npm run e2e`, not vitest.
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
