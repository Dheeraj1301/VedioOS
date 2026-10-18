import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const fixture = JSON.parse(process.env.PROJECT_FILTER_BROWSER_FIXTURE);
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const page = await browser.newPage({viewport: {width: 1280, height: 900}});

try {
  await page.goto(`${fixture.base}/login/`);
  await page.getByLabel('Email').fill(fixture.email);
  await page.getByLabel('Password', {exact: true}).fill(fixture.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(`${fixture.base}/client/`);
  await page.goto(`${fixture.base}/client/projects/`);

  const filter = page.getByLabel('Filter by status');
  assert.equal(await filter.inputValue(), 'all');
  assert.equal(await page.locator('[data-project-row]:visible').count(), 3);
  const url = page.url();

  await filter.selectOption('ongoing');
  assert.equal(page.url(), url);
  assert.equal(await page.locator('[data-project-row]:visible').count(), 1);
  assert.equal(await page.getByText('Ongoing browser project').isVisible(), true);

  await filter.selectOption('cancelled');
  assert.equal(page.url(), url);
  assert.equal(await page.locator('[data-project-row]:visible').count(), 0);
  assert.equal(await page.getByText('No projects found with this status.').isVisible(), true);

  await filter.selectOption('all');
  assert.equal(await page.locator('[data-project-row]:visible').count(), 3);
  assert.equal(await page.getByText('No projects found with this status.').isHidden(), true);
  console.log('PASS: project status filter updates instantly, keeps the URL, and shows its empty state.');
} finally {
  await browser.close();
}
