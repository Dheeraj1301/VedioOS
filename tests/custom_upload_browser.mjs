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

try {
  await page.goto(`${base}/login/`);
  await page.getByLabel('Email').fill(fixture.client.email);
  await page.getByLabel('Password', {exact: true}).fill(fixture.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(`${base}/client/`);

  await page.goto(`${base}/client/new-order/?new=1`);
  await page.getByText('Customize my edit', {exact: true}).click();
  await page.getByLabel('Reel duration').selectOption('30_50');
  await page.getByLabel('Project name').fill(`Custom upload ${runId}`);
  await page.getByLabel('Describe the edit').fill('Synthetic custom-upload regression check.');
  await page.locator('#upload-inspiration').setInputFiles({
    name: filename,
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, ...Buffer.alloc(1024, 73), 0xff, 0xd9]),
  });
  await page.getByRole('button', {name: /Save and Proceed/}).click();
  await page.waitForURL(/\/client\/checkout\/[a-f0-9-]+\/$/, {timeout: 60000});
  await page.getByRole('heading', {name: 'Your customized quotation'}).waitFor();

  const projectId = page.url().split('/').filter(Boolean).at(-1);
  const projectResponse = await context.request.get(`${base}/api/projects/${projectId}/`);
  assert.equal(projectResponse.status(), 200);
  const project = await projectResponse.json();
  const uploaded = project.files.find(file => file.filename === filename);
  assert(uploaded, 'Completed inspiration file is missing from project metadata');
  assert.equal(uploaded.category, 'reference');
  console.log(`PASS: custom draft ${projectId} saved, inspiration upload linked, and quotation opened.`);
} finally {
  await browser.close();
}
