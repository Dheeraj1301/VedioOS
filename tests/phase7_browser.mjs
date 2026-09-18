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
  await page.getByLabel('Password', {exact: true}).fill(f.password);
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
  await page.goto(`${f.base}/client/projects/${f.project}/`);
  await noOverflow();
  const bytes = Buffer.concat([Buffer.from('00000018ftypmp42'), Buffer.alloc(1024 * 1024, 81)]);
  await page.locator('#upload-files').setInputFiles({name: 'phase7-mobile-original.mp4', mimeType: 'video/mp4', buffer: bytes});
  await page.getByRole('button', {name: 'Upload originals'}).click();
  await page.getByText('phase7-mobile-original.mp4', {exact: true}).waitFor({timeout: 60000});
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
  console.log('PASS: 390px and 320px project views, mobile original upload/download integrity, labeled message forms, shared/internal message isolation, admin audit timeline, no page errors.');
} catch (error) {
  await page.screenshot({path: '.runtime/screenshots/phase7-failure.png', fullPage: true});
  console.error('Phase 7 browser flow failed:', error.message);
  console.error('Visible page:', await page.locator('body').innerText());
  process.exitCode = 1;
} finally {
  await browser.close();
}
