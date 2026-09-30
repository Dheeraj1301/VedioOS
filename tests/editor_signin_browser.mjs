import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";

import { chromium } from "@playwright/test";

const base = process.env.BASE_URL || "http://127.0.0.1:8000";
const fixture = JSON.parse(await readFile(".runtime/browser-fixture.json", "utf8"));
const browser = await chromium.launch({ headless: true, channel: "msedge" });
const errors = [];

async function regularLogin(email, expectedRole) {
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`${base}/login/`);
  await page.getByLabel("Email or editor ID").fill(email);
  await page.locator('input[name="password"]').fill(fixture.password);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(`${base}/${expectedRole}/`);
  await context.close();
}

try {
  await mkdir(".runtime/screenshots", { recursive: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto(base);
  const editorEntry = page.getByRole("link", { name: /Editor Sign In/ });
  assert.equal(await editorEntry.getAttribute("href"), "/editor/signin/");
  await editorEntry.click();
  await page.waitForURL(`${base}/editor/signin/`);

  await page.getByLabel("Email or editor ID").fill(fixture.editor.login_id);
  await page.locator('input[name="password"]').fill("wrong-password");
  await page.getByRole("button", { name: "Editor Sign In" }).click();
  await page.getByText(/Please enter a correct email and password/).waitFor();

  await page.getByLabel("Email or editor ID").fill(fixture.editor.login_id);
  await page.locator('input[name="password"]').fill(fixture.password);
  await page.getByRole("button", { name: "Editor Sign In" }).click();
  await page.waitForURL(`${base}/editor/`);
  await page.screenshot({
    path: ".runtime/screenshots/editor-signin-success.png",
    fullPage: true,
  });
  await context.close();

  const deniedContext = await browser.newContext();
  const deniedPage = await deniedContext.newPage();
  deniedPage.on("pageerror", (error) => errors.push(error.message));
  await deniedPage.goto(`${base}/editor/signin/`);
  await deniedPage.getByLabel("Email or editor ID").fill(fixture.client.email);
  await deniedPage.locator('input[name="password"]').fill(fixture.password);
  await deniedPage.getByRole("button", { name: "Editor Sign In" }).click();
  await deniedPage.getByText(/This sign-in is for editor accounts/).waitFor();
  assert.equal(deniedPage.url(), `${base}/editor/signin/`);
  await deniedContext.close();

  await regularLogin(fixture.client.email, "client");
  await regularLogin(fixture.admin.email, "admin");
  assert.deepEqual(errors, []);

  console.log(
    "PASS: Editor Sign In opens /editor/signin/; invalid credentials show an error; " +
      "editor ID reaches /editor/; client credentials are rejected; regular client/admin " +
      "sign-in reaches the correct dashboard; no page errors.",
  );
} catch (error) {
  console.error(`Browser verification failed: ${error.message}`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
