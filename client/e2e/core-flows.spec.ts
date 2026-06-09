import { test, expect, type Page } from "@playwright/test";

/**
 * Core file-browser flows against a live open mount (scripts/e2e.sh):
 * browse, upload (full browser→relay→tunnel→agent round trip), text
 * preview, and folder creation + navigation.
 *
 * These specs double as the pre/post safety net for the App.tsx context
 * refactor — they exercise the wiring the refactor moves around.
 */

const OPEN_CODE = requireEnv("E2E_OPEN_CODE");
const OPEN_FILE = "hello-open.txt"; // seeded by scripts/e2e.sh

function requireEnv(name: string): string {
  const v = process.env[name];
  if (v === undefined || v === "") {
    throw new Error(`Missing required env ${name} (run via scripts/e2e.sh)`);
  }
  return v;
}

async function gotoMount(page: Page): Promise<void> {
  await page.goto(`/m/${OPEN_CODE}/`);
  // The file list renders rows inside a table once loaded.
  await expect(page.getByText(OPEN_FILE)).toBeVisible({ timeout: 10_000 });
}

test("browse: open mount lists the seeded file", async ({ page }) => {
  await gotoMount(page);
  await expect(page.getByText(OPEN_FILE)).toBeVisible();
});

test("upload: a file round-trips through the tunnel and appears in the list", async ({
  page,
}) => {
  await gotoMount(page);

  const name = `e2e-upload-${Date.now()}.txt`;
  // The Upload button opens a hidden file input — set files on the input.
  await page.setInputFiles('input[type="file"][multiple]', {
    name,
    mimeType: "text/plain",
    buffer: Buffer.from("uploaded through the tunnel"),
  });

  await expect(page.getByText(name)).toBeVisible({ timeout: 15_000 });
});

test("preview: clicking a text file name opens the preview with content", async ({
  page,
}) => {
  await gotoMount(page);

  // Single click on the file name opens the preview modal.
  await page.getByText(OPEN_FILE).click();
  // PreviewModal fetches the text and renders it (seeded by scripts/e2e.sh).
  await expect(page.getByText("open mount payload")).toBeVisible({
    timeout: 10_000,
  });
});

test("folders: create a folder and navigate into it", async ({ page }) => {
  await gotoMount(page);

  const folder = `e2e-folder-${Date.now()}`;
  await page.getByRole("button", { name: /new folder/i }).click();
  await page.getByPlaceholder("Folder name").fill(folder);
  await page.getByRole("button", { name: /^create$/i }).click();

  const row = page.getByText(folder);
  await expect(row).toBeVisible({ timeout: 10_000 });

  // Navigate in (double-click a directory row) — list should be empty-ish
  // and the URL should carry ?path=
  await row.dblclick();
  await expect(page).toHaveURL(new RegExp(`path=${folder}`), {
    timeout: 10_000,
  });
});
