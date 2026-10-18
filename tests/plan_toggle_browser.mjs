import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const fixture = JSON.parse(process.env.PLAN_TOGGLE_BROWSER_FIXTURE);
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const page = await browser.newPage({viewport: {width: 1280, height: 900}});

try {
  await page.goto(`${fixture.base}/login/`);
  await page.getByLabel('Email').fill(fixture.email);
  await page.getByLabel('Password', {exact: true}).fill(fixture.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(`${fixture.base}/client/`);
  await page.goto(`${fixture.base}/client/new-order/?new=1`);

  const plan = page.locator(`input[name="order_choice"][value="plan:${fixture.plan_id}"]`);
  await plan.click();
  assert.equal(await plan.isChecked(), true);
  await plan.click();
  await page.waitForFunction(() => !document.querySelector('input[name="order_choice"]:checked'));
  assert.equal(await plan.isChecked(), false);

  const custom = page.locator('input[name="order_choice"][value="custom"]');
  await custom.click();
  await page.getByLabel('Project name').fill('Preserved toggle brief');
  await page.getByLabel('Describe the edit').fill('Keep this text while no plan is selected.');
  await page.locator('#upload-inspiration').setInputFiles({
    name: 'preserved-reference.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0xff, 0xd9]),
  });
  await custom.click();
  await page.waitForFunction(() => !document.querySelector('input[name="order_choice"]:checked'));
  assert.equal(await page.locator('[data-custom-fields]').isHidden(), true);
  assert.equal(await page.getByLabel('Project name').inputValue(), 'Preserved toggle brief');
  assert.equal(await page.getByLabel('Describe the edit').inputValue(), 'Keep this text while no plan is selected.');
  assert.equal(await page.locator('#upload-inspiration').evaluate(input => input.files.length), 1);

  await custom.click();
  assert.equal(await page.locator('[data-custom-fields]').isVisible(), true);
  assert.equal(await page.getByLabel('Project name').inputValue(), 'Preserved toggle brief');
  assert.equal(await page.locator('#upload-inspiration').evaluate(input => input.files.length), 1);
  console.log('PASS: fixed and Custom cards toggle off; Custom fields and selected files survive deselect/reselect.');
} finally {
  await browser.close();
}
