import { test, expect, type Page, type Browser } from "@playwright/test";

/**
 * E2E coverage of the relay user-authentication feature against a live
 * stack (scripts/e2e.sh). Covered: signup, login (+wrong password),
 * guest access to an open mount, unauthenticated redirect on a restricted
 * mount, and the restricted access-request -> admin-approval -> access
 * grant flow.
 */

const OPEN_CODE = requireEnv("E2E_OPEN_CODE");
const RESTRICTED_CODE = requireEnv("E2E_RESTRICTED_CODE");

// Seeded by scripts/e2e.sh via POST /auth/signup. admin is in RELAY_ADMIN_USERS.
const ADMIN = { user: "admin", pass: "pw-admin-1" };
const ALICE = { user: "alice", pass: "pw-alice-1" }; // restricted mount owner
const BOB = { user: "bob", pass: "pw-bob-1" }; // logged-in, not allowlisted

const OPEN_FILE = "hello-open.txt";
const RESTRICTED_FILE = "secret-restricted.txt";

function requireEnv(name: string): string {
  const v = process.env[name];
  if (v === undefined || v === "") {
    throw new Error(`Missing required env ${name} (run via scripts/e2e.sh)`);
  }
  return v;
}

function mountPath(code: string): string {
  return `/m/${code}/`;
}

async function login(page: Page, user: string, pass: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Password").fill(pass);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

test("signup: a new user can self-register and is logged in", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  const username = `carol_${Date.now()}`;

  await page.goto("/signup");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill("pw-carol-1");
  await page.getByRole("button", { name: "Create account" }).click();

  // SignupPage signs up then logs in, then redirects to nextTarget() ("/").
  await expect(page).not.toHaveURL(/\/signup/);
  const cookies = await context.cookies();
  expect(cookies.some((c) => c.name === "wfs_session")).toBe(true);

  await context.close();
});

test("login: wrong password shows an error, correct password succeeds", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto("/login");
  await page.getByLabel("Username").fill(ALICE.user);
  await page.getByLabel("Password").fill("definitely-wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid username or password")).toBeVisible();
  await expect(page).toHaveURL(/\/login/);

  await page.getByLabel("Password").fill(ALICE.pass);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);

  await context.close();
});

test("open mount: guest (no session) can browse without logging in", async ({
  browser,
}) => {
  const context = await browser.newContext(); // no cookies
  const page = await context.newPage();

  // Direct anonymous access to an open mount is allowed.
  await page.goto(mountPath(OPEN_CODE));
  await expect(page.getByText(OPEN_FILE)).toBeVisible();

  // "Continue as guest" from the login page reaches the same open mount.
  await page.goto(`/login?next=${encodeURIComponent(mountPath(OPEN_CODE))}`);
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await expect(page).toHaveURL(new RegExp(`/m/${OPEN_CODE}/`));
  await expect(page.getByText(OPEN_FILE)).toBeVisible();

  await context.close();
});

test("restricted mount: anonymous access redirects to /login?next=", async ({
  browser,
}) => {
  const context = await browser.newContext(); // no cookies
  const page = await context.newPage();

  await page.goto(mountPath(RESTRICTED_CODE));
  await expect(page).toHaveURL(/\/login\?next=/);
  expect(decodeURIComponent(page.url())).toContain(mountPath(RESTRICTED_CODE));

  await context.close();
});

test("restricted mount: denied user requests access, admin approves, access granted", async ({
  browser,
}: {
  browser: Browser;
}) => {
  // --- Bob: logged in but not allowlisted -> 403 denial page ---
  const bobCtx = await browser.newContext();
  const bob = await bobCtx.newPage();
  await login(bob, BOB.user, BOB.pass);

  await bob.goto(mountPath(RESTRICTED_CODE));
  await expect(bob.getByText(/Access Denied/i)).toBeVisible();

  // --- Bob submits an access request via the /403 page ---
  await bob.goto(`/403?code=${RESTRICTED_CODE}`);
  await expect(bob.getByLabel("Mount code")).toHaveValue(RESTRICTED_CODE);
  await bob.getByRole("button", { name: "Request access" }).click();
  await expect(
    bob.getByText("Request sent. The owner or an admin will review it."),
  ).toBeVisible();

  // --- Admin approves the pending request in the dashboard ---
  const adminCtx = await browser.newContext();
  const admin = await adminCtx.newPage();
  await login(admin, ADMIN.user, ADMIN.pass);
  await admin.goto("/admin");

  // Guard: confirm we actually have the admin view, not the denied page.
  await expect(
    admin.getByText("Admin privileges required."),
  ).toHaveCount(0);
  await expect(
    admin.getByRole("heading", { name: "Pending access requests" }),
  ).toBeVisible();

  // Each pending request is an <li> "<user> → mount <code>". Filtering by
  // the code disambiguates it from the bob entry in the Users list.
  const requestRow = admin
    .locator("li")
    .filter({ hasText: BOB.user })
    .filter({ hasText: RESTRICTED_CODE });
  await expect(requestRow).toBeVisible();
  await requestRow.getByRole("button", { name: "Approve (read)" }).click();
  // Row clears once resolved (dashboard reloads pending requests).
  await expect(requestRow).toHaveCount(0);

  // --- Bob can now browse the restricted mount ---
  await bob.goto(mountPath(RESTRICTED_CODE));
  await expect(bob.getByText(RESTRICTED_FILE)).toBeVisible();

  await bobCtx.close();
  await adminCtx.close();
});
