import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";

import { chromium } from "@playwright/test";

const base = process.env.BASE_URL || "http://127.0.0.1:8000";
const fixture = JSON.parse(await readFile(".runtime/browser-fixture.json", "utf8"));
const browser = await chromium.launch({ headless: true, channel: "msedge" });
const errors = [];
let context;
let page;

try {
  await mkdir(".runtime/screenshots", { recursive: true });
  context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto(`${base}/editor/signin/`);
  await page.getByLabel("Email or editor ID").fill(fixture.editor.login_id);
  await page.locator('input[name="password"]').fill(fixture.password);
  await page.getByRole("button", { name: "Editor Sign In" }).click();
  await page.waitForURL(`${base}/editor/`);

  await page.goto(`${base}/editor/availability/`);
  await page.getByRole("heading", { name: "Your availability." }).waitFor();
  await page.getByText(/Available.*no active projects/).waitFor();
  assert.equal(await page.locator("select").count(), 0);
  assert.equal(await page.getByRole("button", { name: /save/i }).count(), 0);

  const response = await context.request.get(`${base}/api/editor/availability/`);
  assert.equal(response.status(), 200);
  assert.deepEqual(await response.json(), {
    status: "available",
    label: "Available",
    icon: "✅",
    active_count: 0,
    summary: "Available — no active projects",
  });

  await page.route("**/api/editor/availability/", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        status: "unavailable",
        label: "Unavailable",
        icon: "🔴",
        active_count: 2,
        summary: "Unavailable — 2 active projects",
      },
    });
  });
  await page
    .locator("[data-availability-status]")
    .filter({ hasText: "Unavailable — 2 active projects" })
    .waitFor({ timeout: 7000 });
  await page.locator(".availability-badge.is-unavailable").waitFor();
  await page.screenshot({
    path: ".runtime/screenshots/editor-availability.png",
    fullPage: true,
  });
  assert.deepEqual(errors, []);

  console.log(
    "PASS: derived availability is read-only, API-backed, and changes from Available to " +
      "Unavailable without a page refresh; no browser errors.",
  );
} catch (error) {
  console.error(`Browser verification failed: ${error.message}`);
  console.error(`Current URL: ${page?.url?.() || "unavailable"}`);
  console.error(`Visible text: ${await page?.locator?.("body")?.innerText?.().catch(() => "unavailable")}`);
  process.exitCode = 1;
} finally {
  await Promise.race([
    context?.close(),
    new Promise((resolve) => setTimeout(resolve, 3000)),
  ]);
  await Promise.race([
    browser.close(),
    new Promise((resolve) => setTimeout(resolve, 3000)),
  ]);
}

process.exit(process.exitCode || 0);
