import { chromium } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

// Uses an existing synthetic account transferred from the local Day 1 tests.
// Does not create new identities or projects in the connected cloud database.
const admin = JSON.parse(await readFile('.runtime/browser-fixture.json', 'utf8'));
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const page = await browser.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto('http://127.0.0.1:8000/login/');
  await page.getByLabel('Email').fill(admin.email);
  await page.getByLabel('Password', {exact: true}).fill(admin.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL('**/admin/', {timeout: 60000});
  await page.getByRole('heading', {name: 'Studio overview.'}).waitFor();
  await page.goto('http://127.0.0.1:8000/admin/projects/');
  assert.ok(await page.locator('.project-row').count() >= 2);
  await page.screenshot({path: '.runtime/screenshots/supabase-admin.png', fullPage: true});
  await page.goto('http://127.0.0.1:8000/admin/pricing/');
  await page.getByRole('heading', {name: 'Plans & pricing.'}).waitFor();
  assert.equal(await page.locator('.catalog-grid article').count(), 3);
  await page.screenshot({path: '.runtime/screenshots/phase3-live-catalog.png', fullPage: true});
  await page.getByRole('button', {name: 'Log out'}).filter({visible: true}).click();
  await page.waitForURL('http://127.0.0.1:8000/');
  assert.deepEqual(errors, []);
  console.log('PASS: live browser login, PostgreSQL-backed dashboard, migrated projects, catalog slots, and logout. No page errors.');
} finally {await browser.close();}
