import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile } from 'node:fs/promises';

const f = JSON.parse(process.env.PHASE7_BROWSER_FIXTURE);
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const page = await browser.newPage({viewport: {width: 390, height: 844}, acceptDownloads: true});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {if (response.status() >= 500) errors.push(`HTTP ${response.status()}`);});

async function login(email) {
  await page.goto(`${f.base}/login/`);
  await page.getByLabel('Email').fill(email);
  const password = page.getByLabel('Password', {exact: true});
  const toggle = page.getByRole('button', {name: 'Show password'}).first();
  await toggle.click();
  assert.equal(await password.getAttribute('type'), 'text');
  await page.getByRole('button', {name: 'Hide password'}).first().click();
  assert.equal(await password.getAttribute('type'), 'password');
  await password.fill(f.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(/\/(client|editor|admin)\/$/);
}
async function logout() {
  await page.getByRole('button', {name: 'Log out'}).filter({visible: true}).click();
  await page.waitForURL(`${f.base}/`);
}
async function noOverflow() {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Horizontal overflow');
}
try {
  await mkdir('.runtime/screenshots', {recursive: true});
  await login(f.client);
  await page.goto(`${f.base}/client/projects/00000000-0000-0000-0000-000000000000/`);
  await page.getByRole('heading', {name: 'This page could not be found.'}).waitFor();
  await page.getByRole('link', {name: 'Return to workspace'}).waitFor();
  await noOverflow();
  await page.screenshot({path: '.runtime/screenshots/phase7-error-recovery-mobile.png', fullPage: true});
  await page.goto(`${f.base}/client/projects/${f.project}/`);
  await noOverflow();
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(() => document.activeElement?.classList.contains('skip-link')), true);
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(() => document.activeElement?.id), 'main');
  assert.equal(await page.locator('#upload-status').getAttribute('aria-live'), 'polite');
  assert.equal(await page.locator('#download-status').getAttribute('aria-live'), 'polite');
  await page.locator('#upload-files').setInputFiles({name: 'unsupported.txt', mimeType: 'text/plain', buffer: Buffer.from('synthetic')});
  await page.getByRole('button', {name: 'Upload source files'}).click();
  await page.locator('#upload-status[role="alert"]').waitFor();
  assert.equal(await page.getByRole('button', {name: 'Upload source files'}).isEnabled(), true);
  const bytes = Buffer.concat([Buffer.from('00000018ftypmp42'), Buffer.alloc(1024 * 1024, 81)]);
  await page.locator('#upload-files').setInputFiles({name: 'phase7-mobile-original.mp4', mimeType: 'video/mp4', buffer: bytes});
  await page.getByRole('button', {name: 'Upload source files'}).click();
  await page.getByText('phase7-mobile-original.mp4', {exact: true}).waitFor({timeout: 60000});
  await page.locator('#inspiration-files').setInputFiles({name: 'phase7-inspiration.mp4', mimeType: 'video/mp4', buffer: Buffer.from('synthetic-inspiration-video')});
  await page.getByRole('button', {name: 'Upload inspiration'}).click();
  await page.getByText('phase7-inspiration.mp4', {exact: true}).waitFor({timeout: 60000});
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', {name: 'Download'}).first().click(),
  ]);
  const result = await readFile(await download.path());
  assert.equal(createHash('sha256').update(result).digest('hex'), createHash('sha256').update(bytes).digest('hex'));
  await page.getByLabel('Message to client and team').fill('Mobile client update');
  await page.getByRole('button', {name: 'Send message'}).click();
  await page.getByText('Mobile client update', {exact: true}).waitFor();
  await noOverflow();
  await page.screenshot({path: '.runtime/screenshots/phase7-client-mobile.png', fullPage: true});
  await page.goto(`${f.base}/orders/notifications/`);
  await page.getByRole('link', {name: 'Older updates'}).click();
  await page.getByRole('button', {name: 'Mark read'}).first().click();
  await page.waitForURL(/\/orders\/notifications\/\?before=/);
  await noOverflow();
  await page.screenshot({path: '.runtime/screenshots/phase7-notifications-mobile.png', fullPage: true});
  await page.setViewportSize({width: 320, height: 700});
  await noOverflow();
  await logout();

  await login(f.admin);
  await page.goto(`${f.base}/admin/projects/${f.project}/`);
  await page.getByLabel('Note for the project team only').fill('Staff-only scheduling detail');
  await page.getByRole('button', {name: 'Save internal note'}).click();
  await page.getByText('Staff-only scheduling detail', {exact: true}).waitFor();
  await noOverflow();
  await page.goto(`${f.base}/admin/audit/`);
  await page.getByText('project.message_posted', {exact: true}).first().waitFor();
  await noOverflow();
  await page.screenshot({path: '.runtime/screenshots/phase7-audit-mobile.png', fullPage: true});
  await logout();

  await login(f.client);
  await page.goto(`${f.base}/client/projects/${f.project}/`);
  assert.equal(await page.getByText('Staff-only scheduling detail', {exact: true}).count(), 0);
  assert.equal(await page.getByRole('button', {name: 'Save internal note'}).count(), 0);
  await logout();

  await login(f.editor);
  await page.goto(`${f.base}/editor/projects/${f.project}/`);
  await page.getByText('Staff-only scheduling detail', {exact: true}).waitFor();
  await page.setViewportSize({width: 390, height: 844});
  await noOverflow();
  await page.screenshot({path: '.runtime/screenshots/phase7-editor-mobile.png', fullPage: true});
  assert.deepEqual(errors, []);
  console.log('PASS: 390px and 320px project views, password visibility, keyboard navigation, separate inspiration upload, original-byte integrity, accessible retry, message isolation, notifications, audit timeline, no page errors.');
} catch (error) {
  await page.screenshot({path: '.runtime/screenshots/phase7-failure.png', fullPage: true});
  console.error('Phase 7 browser flow failed:', error.message);
  console.error('Visible page:', await page.locator('body').innerText());
  process.exitCode = 1;
} finally {
  await browser.close();
}
