import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";

import { chromium } from "@playwright/test";

const base = process.env.BASE_URL || "http://127.0.0.1:8000";
const fixture = JSON.parse(await readFile(".runtime/browser-fixture.json", "utf8"));
const browser = await chromium.launch({ headless: true, channel: "msedge" });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));

async function assertBrioPage(path) {
  await page.goto(`${base}${path}`);
  await page.getByRole("link", { name: "BRIO home" }).waitFor();
  assert.match(await page.title(), /BRIO$/);
  assert.equal((await page.locator("body").innerText()).toLowerCase().includes("vedioos"), false);
}

try {
  await mkdir(".runtime/screenshots", { recursive: true });
  await assertBrioPage("/");
  await page.screenshot({ path: ".runtime/screenshots/brio-landing.png", fullPage: true });

  await assertBrioPage("/login/");
  await page.screenshot({ path: ".runtime/screenshots/brio-login.png", fullPage: true });
  await page.getByLabel("Email").fill(fixture.client.email);
  await page.locator('input[name="password"]').fill(fixture.password);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(`${base}/client/`);
  await page.locator(".sidebar .brand", { hasText: "BRIO" }).waitFor();
  assert.equal((await page.locator("body").innerText()).toLowerCase().includes("vedioos"), false);
  await page.screenshot({ path: ".runtime/screenshots/brio-client-sidebar.png", fullPage: true });

  assert.deepEqual(errors, []);
  console.log("PASS: BRIO renders in the live landing page, login, title, and authenticated sidebar with no visible legacy brand or page errors.");
} finally {
  await browser.close();
}
