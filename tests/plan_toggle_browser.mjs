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

  const plan = page.locator(`input[name="order_choice"][value="plan:${fixture.plan_ids[0]}"]`);
  await plan.click();
  assert.equal(await plan.isChecked(), true);
  assert.equal(await page.locator('[data-standard-upload-fields]').isVisible(), true);
  assert.equal(await page.locator('[data-custom-fields]').isHidden(), true);
  assert.equal(await page.getByLabel('Project name').first().isVisible(), true);
  await page.locator('#standard-project-title').fill('Preserved standard plan title');
  await page.locator('#standard-upload-clips').setInputFiles({
    name: 'standard-source.bin', mimeType: 'application/octet-stream', buffer: Buffer.from('source'),
  });
  await page.locator('#standard-upload-inspiration').setInputFiles(
    [1, 2, 3, 4].map(number => ({
      name: `standard-reference-${number}.mp4`,
      mimeType: 'video/mp4',
      buffer: Buffer.from(`reference-${number}`),
    })),
  );
  assert.equal(await page.locator('#standard-upload-inspiration').evaluate(input => input.files.length), 3);
  await page.locator('.standard-brief-inspiration-status').getByText('Max uploads: 3.', {exact: true}).waitFor();
  const secondPlan = page.locator(`input[name="order_choice"][value="plan:${fixture.plan_ids[1]}"]`);
  await secondPlan.click();
  assert.equal(await secondPlan.isChecked(), true);
  assert.equal(await page.locator('#standard-project-title').inputValue(), 'Preserved standard plan title');
  assert.equal(await page.locator('#standard-upload-clips').evaluate(input => input.files.length), 1);
  assert.equal(await page.locator('#standard-upload-inspiration').evaluate(input => input.files.length), 3);
  await secondPlan.click();
  await page.waitForFunction(() => !document.querySelector('input[name="order_choice"]:checked'));
  assert.equal(await secondPlan.isChecked(), false);
  assert.equal(await page.locator('[data-standard-upload-fields]').isHidden(), true);
  assert.equal(await page.locator('#standard-upload-clips').evaluate(input => input.files.length), 1);
  assert.equal(await page.locator('#standard-upload-inspiration').evaluate(input => input.files.length), 3);

  await plan.click();
  assert.equal(await page.locator('[data-standard-upload-fields]').isVisible(), true);
  assert.equal(await page.locator('#standard-upload-clips').evaluate(input => input.files.length), 1);
  await plan.click();

  const custom = page.locator('input[name="order_choice"][value="custom"]');
  await custom.click();
  await page.locator('#id_title').fill('Preserved toggle brief');
  await page.getByLabel('Describe the edit').fill('Keep this text while no plan is selected.');
  await page.locator('#upload-inspiration').setInputFiles({
    name: 'preserved-reference.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0xff, 0xd9]),
  });
  await custom.click();
  await page.waitForFunction(() => !document.querySelector('input[name="order_choice"]:checked'));
  assert.equal(await page.locator('[data-custom-fields]').isHidden(), true);
  assert.equal(await page.locator('#id_title').inputValue(), 'Preserved toggle brief');
  assert.equal(await page.getByLabel('Describe the edit').inputValue(), 'Keep this text while no plan is selected.');
  assert.equal(await page.locator('#upload-inspiration').evaluate(input => input.files.length), 1);

  await custom.click();
  assert.equal(await page.locator('[data-custom-fields]').isVisible(), true);
  assert.equal(await page.locator('#id_title').inputValue(), 'Preserved toggle brief');
  assert.equal(await page.locator('#upload-inspiration').evaluate(input => input.files.length), 1);
  console.log('PASS: standard title and uploads appear immediately, retain state, and enforce the three-reference cap; Custom fields remain unchanged.');
} finally {
  await browser.close();
}
