import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const fixture = JSON.parse(process.env.CUSTOM_FORM_BROWSER_FIXTURE);
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const context = await browser.newContext({viewport: {width: 1280, height: 900}});
const page = await context.newPage();

try {
  await page.goto(`${fixture.base}/login/`);
  await page.getByLabel('Email').fill(fixture.email);
  await page.getByLabel('Password', {exact: true}).fill(fixture.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(`${fixture.base}/client/`);

  await page.goto(`${fixture.base}/client/new-order/?new=1`);
  await page.locator('input[name="order_choice"][value="custom"]').check();
  await page.getByLabel('Project name').fill('Recovery browser brief');
  await page.getByLabel('Describe the edit').fill('Keep this description after validation.');
  await page.getByLabel('Add wording or on-screen text').check();
  await page.getByLabel('Font selection').selectOption('own_font');
  await page.getByLabel('Font style or name').fill('Montserrat');
  await page.getByLabel('Inspiration link').fill('https://example.com/reference');
  await page.getByRole('button', {name: /Save and Proceed/}).click();
  await page.getByText('Choose the expected reel duration.').waitFor();
  assert.equal(await page.getByLabel('Project name').inputValue(), 'Recovery browser brief');
  assert.equal(await page.getByLabel('Font selection').inputValue(), 'own_font');
  assert.equal(await page.getByLabel('Font style or name').inputValue(), 'Montserrat');
  assert.equal(await page.getByLabel('Inspiration link').inputValue(), 'https://example.com/reference');
  await page.getByLabel('Reel duration').selectOption('30_50');

  const files = Array.from({length: 4}, (_, index) => ({
    name: `recovery-reference-${index + 1}.jpg`,
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, ...Buffer.alloc(256, index + 1), 0xff, 0xd9]),
  }));
  await page.locator('#upload-inspiration').setInputFiles(files);
  await page.getByText('Max uploads: 3.', {exact: true}).last().waitFor();
  assert.equal(await page.locator('#upload-inspiration').evaluate(input => input.files.length), 3);

  let interruptedPuts = 0;
  await page.route('**/*', async route => {
    if (route.request().method() === 'PUT' && interruptedPuts < 2) {
      interruptedPuts += 1;
      await route.abort('connectionfailed');
      return;
    }
    await route.continue();
  });
  await page.getByRole('button', {name: /Save and Proceed/}).click();
  const retry = page.getByRole('button', {name: 'Retry failed upload'});
  await retry.waitFor({state: 'visible', timeout: 60000});
  await retry.click();
  await page.waitForURL(/\/client\/projects\/[a-f0-9-]+\/edit\/$/, {timeout: 60000});
  await page.getByText('recovery-reference-1.jpg', {exact: true}).waitFor({timeout: 60000});
  const projectId = page.url().match(/\/client\/projects\/([a-f0-9-]+)\/edit\//i)?.[1];
  assert(projectId, 'Saved project ID is missing after upload recovery.');

  const beforeRemoval = await page.evaluate(async id => {
    const response = await fetch(`/api/projects/${id}/`);
    return {status: response.status, body: await response.json()};
  }, projectId);
  assert.equal(beforeRemoval.status, 200, JSON.stringify(beforeRemoval.body));
  const references = beforeRemoval.body.files.filter(file => file.category === 'reference');
  assert.equal(references.length, 3);
  assert(!references.some(file => file.filename === 'recovery-reference-4.jpg'));
  await page.getByRole('button', {name: 'Remove recovery-reference-1.jpg'}).click();
  await page.getByText('recovery-reference-1.jpg removed from this brief.').waitFor();
  const afterRemoval = await page.evaluate(async id => {
    const response = await fetch(`/api/projects/${id}/`);
    return {status: response.status, body: await response.json()};
  }, projectId);
  assert.equal(afterRemoval.status, 200, JSON.stringify(afterRemoval.body));
  assert.equal(afterRemoval.body.files.filter(file => file.category === 'reference').length, 2);
  console.log('PASS: invalid form state persisted; interrupted upload exposed Retry; retry saved 3/4 references; one persisted reference was removed.');
} finally {
  await browser.close();
}
