import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';

const base = process.env.BASE_URL || 'http://127.0.0.1:8000';
const fixture = JSON.parse(await readFile('.runtime/browser-fixture.json', 'utf8'));
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const runId = randomUUID().slice(0, 8);
const password = `Creator-${randomUUID()}!`;
const pendingClientEmail = `browser-pending-${runId}@example.test`;
await mkdir('.runtime/screenshots', {recursive: true});

async function login(email, value) {
  await page.goto(`${base}/login/`);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', {exact: true}).fill(value);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(/\/(client|editor|admin)\/$/);
}
async function logout() {
  await page.getByRole('button', {name: 'Log out'}).filter({visible: true}).click();
  await page.waitForURL(`${base}/`);
}
async function noOverflow() {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Horizontal overflow');
}
try {
  await page.goto(base);
  await page.getByRole('heading', {name: 'You shoot. We make it worth watching.'}).waitFor();
  await page.screenshot({path: '.runtime/screenshots/landing-desktop.png', fullPage: true});
  await page.setViewportSize({width: 390, height: 844});
  await noOverflow();
  await page.screenshot({path: '.runtime/screenshots/landing-mobile.png', fullPage: true});
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto(`${base}/register/`);
  await page.getByLabel('Name', {exact: true}).fill('Browser Test Creator');
  await page.getByLabel('Email').fill(pendingClientEmail);
  await page.getByLabel('Password', {exact: true}).fill(password);
  await page.getByLabel('Password confirmation').fill(password);
  await page.getByRole('button', {name: 'Create account'}).click();
  await page.waitForURL(`${base}/verify-email/`);
  await page.getByRole('heading', {name: 'Verify your email.'}).waitFor();
  await page.getByRole('button', {name: 'Resend verification link'}).waitFor();
  await login(fixture.client.email, fixture.password);
  await page.screenshot({path: '.runtime/screenshots/client-desktop.png', fullPage: true});
  assert.equal((await context.request.get(`${base}/api/areas/admin/`)).status(), 403);
  assert.equal((await context.request.get(`${base}/api/areas/editor/`)).status(), 403);
  await page.goto(`${base}/client/new-order/`);
  await page.getByText('Customize my edit', {exact: true}).click();
  await page.getByLabel('Reel duration').selectOption('30_50');
  await page.getByLabel('Project name').fill(`My first reel ${runId}`);
  await page.getByLabel('What would you like us to edit?').fill('Synthetic browser test: clean cuts, captions, and warm colors.');
  await page.getByLabel('Inspiration and reference notes').fill('A calm, story-led reel.');
  await page.getByRole('button', {name: 'Save & add files'}).click();
  await page.waitForURL(/\/client\/projects\/[a-f0-9-]+\/$/);
  const projectUrl = page.url();
  const projectId = projectUrl.split('/').filter(Boolean).at(-1);
  const bytes = Buffer.concat([Buffer.from('00000018ftypmp42'), Buffer.alloc(5 * 1024 * 1024, 73)]);
  await page.locator('#upload-files').setInputFiles({name: 'browser-original.mp4', mimeType: 'video/mp4', buffer: bytes});
  await page.getByRole('button', {name: 'Upload source files'}).click();
  await page.getByText('browser-original.mp4', {exact: true}).waitFor({timeout: 60000});
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', {name: 'Download'}).click()]);
  const downloaded = await readFile(await download.path());
  assert.equal(createHash('sha256').update(downloaded).digest('hex'), createHash('sha256').update(bytes).digest('hex'));
  await page.screenshot({path: '.runtime/screenshots/project-desktop.png', fullPage: true});
  await page.setViewportSize({width: 390, height: 844});
  await noOverflow();
  await page.screenshot({path: '.runtime/screenshots/project-mobile.png', fullPage: true});
  await logout();
  await page.setViewportSize({width: 1440, height: 1000});
  await login(fixture.client.email, fixture.password);
  await logout();
  await login(fixture.editor.login_id, fixture.password);
  await page.getByText('Your editor account is awaiting approval.').waitFor();
  assert.equal((await context.request.get(`${base}/api/projects/${projectId}/`)).status(), 404);
  assert.equal((await context.request.get(`${base}/api/areas/client/`)).status(), 403);
  assert.equal((await context.request.get(`${base}/api/areas/admin/`)).status(), 403);
  await page.screenshot({path: '.runtime/screenshots/editor-desktop.png', fullPage: true});
  await page.goto(`${base}/editor/availability/`);
  await page.getByLabel('Status').selectOption('on_leave');
  await page.getByRole('button', {name: 'Save availability'}).click();
  await page.getByText('Availability updated.', {exact: false}).waitFor();
  await logout();
  await login(fixture.editor.login_id, fixture.password);
  await logout();
  await login(fixture.admin.email, fixture.password);
  await page.screenshot({path: '.runtime/screenshots/admin-desktop.png', fullPage: true});
  await page.goto(`${base}/admin/editors/`);
  const application = page.locator('.data-list > li').filter({hasText: fixture.editor.email});
  await application.getByRole('combobox').selectOption('intermediate');
  await application.getByRole('button', {name: 'Approve level'}).click();
  await page.getByText('Browser Test Editor approved as Intermediate.').waitFor();
  await page.setViewportSize({width: 390, height: 844});
  await noOverflow();
  await page.screenshot({path: '.runtime/screenshots/admin-mobile.png', fullPage: true});
  assert.deepEqual(errors, []);
  console.log('PASS: desktop/mobile UI, client verification pending flow, editor-ID/client/admin login, admin approval, role isolation, project creation, direct upload and byte-identical original download. No page errors.');
} catch (error) {
  await page.screenshot({path: '.runtime/screenshots/failure.png', fullPage: true});
  console.error('Browser flow failed:', error.message);
  console.error('Visible status:', await page.locator('body').innerText());
  process.exitCode = 1;
} finally {await browser.close();}
