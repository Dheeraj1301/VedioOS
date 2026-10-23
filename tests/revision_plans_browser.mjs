import assert from 'node:assert/strict';

import { chromium } from '@playwright/test';

const fixture = JSON.parse(process.env.REVISION_PLANS_BROWSER_FIXTURE);
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const page = await browser.newPage({viewport: {width: 1280, height: 900}});

try {
  await page.goto(`${fixture.base}/login/`);
  await page.getByLabel('Email or editor ID').fill(fixture.admin_email);
  await page.locator('input[name="password"]').fill(fixture.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(`${fixture.base}/admin/`);
  await page.goto(`${fixture.base}/admin/pricing/`);
  assert.equal(await page.getByRole('link', {name: /Configure revision plan/}).count(), 3);
  for (let slot = 1; slot <= 3; slot += 1) {
    await page.getByRole('link', {name: `Configure revision plan ${slot} →`}).click();
    await page.getByLabel('Plan name / title').fill(`Revision option ${slot}`);
    await page.getByLabel('Currency').selectOption('INR');
    await page.getByLabel('Revision plan price (₹)').fill(`${slot}00.00`);
    await page.getByLabel('Description / details').fill(`Published revision details ${slot}.`);
    await page.getByLabel('Active').check();
    await page.getByRole('button', {name: /Save configuration/}).click();
    await page.waitForURL(`${fixture.base}/admin/pricing/`);
  }
  await page.getByRole('button', {name: 'Log out'}).click();
  await page.waitForURL(`${fixture.base}/`);
  await page.goto(`${fixture.base}/login/`);
  await page.getByLabel('Email or editor ID').fill(fixture.email);
  await page.locator('input[name="password"]').fill(fixture.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(`${fixture.base}/client/`);
  await page.getByRole('link', {name: 'Revisions'}).click();
  await page.waitForURL(`${fixture.base}/client/revisions/`);

  const cards = page.locator('[data-revision-plan]');
  assert.equal(await cards.count(), 3);
  await cards.nth(0).click();
  assert.equal(await cards.nth(0).getAttribute('aria-pressed'), 'true');
  await cards.nth(1).click();
  assert.equal(await cards.nth(0).getAttribute('aria-pressed'), 'false');
  assert.equal(await cards.nth(1).getAttribute('aria-pressed'), 'true');
  await cards.nth(1).click();
  assert.equal(await cards.nth(1).getAttribute('aria-pressed'), 'false');
  await page.getByText('No revision plan selected.', {exact: true}).waitFor();
  console.log('PASS: admin configured and published all three revision plans; the client saw them immediately and exclusive selection plus click-again deselection worked.');
} finally {
  await browser.close();
}
