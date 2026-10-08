import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';

const base = process.env.BASE_URL || 'http://127.0.0.1:8000';
const fixture = JSON.parse(await readFile('.runtime/browser-fixture.json', 'utf8'));
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
const page = await context.newPage();
const runId = randomUUID().slice(0, 8);
const filename = `custom-inspiration-${runId}.jpg`;
const expectCheckout = process.env.EXPECT_CHECKOUT !== '0';

try {
  await page.goto(`${base}/login/`);
  await page.getByLabel('Email').fill(fixture.client.email);
  await page.getByLabel('Password', {exact: true}).fill(fixture.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(`${base}/client/`);

  await page.goto(`${base}/client/new-order/?new=1`);
  await page.locator('input[name="order_choice"][value="custom"]').check();
  await page.getByLabel('Reel duration').selectOption('30_50');
  await page.getByLabel('Project name').fill(`Custom upload ${runId}`);
  await page.getByLabel('Describe the edit').fill('Synthetic custom-upload regression check.');
  await page.locator('#upload-inspiration').setInputFiles({
    name: filename,
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, ...Buffer.alloc(1024, 73), 0xff, 0xd9]),
  });
  await page.getByRole('button', {name: /Save and Proceed/}).click();
  await page.waitForURL(
    expectCheckout
      ? /\/client\/checkout\/[a-f0-9-]+\/$/
      : /\/client\/projects\/[a-f0-9-]+\/edit\/$/,
    {timeout: 60000},
  );
  if (expectCheckout) {
    await page.getByRole('heading', {name: 'Your customized quotation'}).waitFor();
    await page.getByRole('button', {name: /Make Payment/}).waitFor();
  } else {
    await page.getByRole('heading', {name: 'Edit your creative brief.'}).waitFor();
  }

  const projectId = page.url().match(/\/client\/(?:projects|checkout)\/([a-f0-9-]+)/i)?.[1];
  assert(projectId, 'Saved project ID is missing from the resulting URL');
  const projectResponse = await context.request.get(`${base}/api/projects/${projectId}/`);
  assert.equal(projectResponse.status(), 200);
  const project = await projectResponse.json();
  const uploaded = project.files.find(file => file.filename === filename);
  assert(uploaded, 'Completed inspiration file is missing from project metadata');
  assert.equal(uploaded.category, 'reference');
  if (expectCheckout && process.env.MAKE_PAYMENT === '1') {
    await page.getByLabel(/I accept this quotation/).check();
    await page.getByRole('button', {name: /Make Payment/}).click();
    await page.waitForURL(new RegExp(`/orders/${projectId}/$`));
    await page.getByRole('heading', {name: 'Order summary'}).waitFor();
    await page.getByText(/Payment was started using|Development payment created/).waitFor();
  }
  console.log(
    `PASS: custom draft ${projectId} saved, inspiration upload linked, and ${
      expectCheckout ? 'quotation opened' : 'pricing fallback returned to the editable brief'
    }.`,
  );
} finally {
  await browser.close();
}
