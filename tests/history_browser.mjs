import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const base = process.env.BASE_URL || 'http://127.0.0.1:8000';
const fixture = JSON.parse(await readFile('.runtime/browser-fixture.json', 'utf8'));
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL });
const page = await (await browser.newContext()).newPage();
let redirects = [];
page.on('response', response => {
  if (response.status() >= 300 && response.status() < 400) redirects.push(new URL(response.url()).pathname);
});

const path = () => new URL(page.url()).pathname;
async function settle(action) {
  redirects = [];
  await action().catch(() => {});
  await page.waitForTimeout(600);
}
const back = () => settle(() => page.goBack({ waitUntil: 'commit', timeout: 3000 }));
const forward = () => settle(() => page.goForward({ waitUntil: 'commit', timeout: 3000 }));

// The login page is a fixed history boundary (DECISIONS.md, 2026-10-30): Back and
// Forward both stay on it without another request.
await page.goto(`${base}/`);
await settle(() => page.locator('a[href="/login/"]').first().click());
assert.equal(path(), '/login/');
await back();
assert.equal(path(), '/login/', 'Back stays on the login page');
assert.deepEqual(redirects, []);
await forward();
assert.equal(path(), '/login/', 'Forward stays on the login page');

// After signing in, Back keeps the same dashboard page without a server redirect.
await page.getByLabel('Email').fill(fixture.client.email);
await page.getByLabel('Password', { exact: true }).fill(fixture.password);
await page.getByRole('button', { name: 'Log in' }).click();
await page.waitForURL(/\/client\/$/);
for (let press = 1; press <= 4; press += 1) {
  await back();
  assert.equal(path(), '/client/', `Back #${press} stays on the dashboard`);
  assert.deepEqual(redirects, [], `Back #${press} does not redirect`);
}

// Inside the workspace, browser history and the in-page Back button stay in sync,
// and the sign-in boundary still holds after visiting another page.
const target = await page.$$eval('a[href^="/client/"]', links =>
  links.map(link => link.getAttribute('href')).find(href => href && href.split('#')[0] !== '/client/'));
await settle(() => page.locator(`a[href="${target}"]`).filter({ visible: true }).first().click());
assert.equal(path(), target);
await settle(() => page.locator('.back-button').filter({ visible: true }).first().click());
assert.equal(path(), '/client/', 'In-page Back matches browser Back');
await forward();
assert.equal(path(), target);
await back();
assert.equal(path(), '/client/');
for (let press = 1; press <= 2; press += 1) {
  await back();
  assert.equal(path(), '/client/', `Back #${press} after returning stays on the dashboard`);
  assert.deepEqual(redirects, [], `Back #${press} after returning does not redirect`);
}

// After logging out, Back stays on the landing page instead of requesting the earlier
// signed-in page and being redirected to /login/?next=...
await settle(() => page.getByRole('button', { name: 'Log out' }).filter({ visible: true }).first().click());
assert.equal(path(), '/');
for (let press = 1; press <= 2; press += 1) {
  await back();
  assert.equal(path(), '/', `Back #${press} after logout stays on the landing page`);
  assert.deepEqual(redirects, [], `Back #${press} after logout does not redirect`);
}

await browser.close();
console.log('History navigation checks passed.');
