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
  await page.getByLabel('Font selection').selectOption('font_inspiration');
  await page.getByLabel('Inspiration link').fill('https://example.com/reference');
  await page.getByLabel('Music preference').selectOption('provide');
  await page.getByLabel('Song Name or Link').fill('Keep this song choice after validation.');
  await page.getByLabel('Revisions needed').selectOption('3-4');
  const clip = {
    name: 'recovery-source.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, ...Buffer.alloc(256, 7), 0xff, 0xd9]),
  };
  const fontReference = {
    name: 'recovery-font.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, ...Buffer.alloc(256, 8), 0xff, 0xd9]),
  };
  const files = Array.from({length: 4}, (_, index) => ({
    name: `recovery-reference-${index + 1}.jpg`,
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, ...Buffer.alloc(256, index + 1), 0xff, 0xd9]),
  }));
  await page.locator('#upload-clips').setInputFiles(clip);
  await page.locator('#upload-inspiration').setInputFiles(files);
  await page.locator('#brief-font-inspiration').setInputFiles(fontReference);
  await page.getByText('Max uploads: 3.', {exact: true}).last().waitFor();
  await page.getByRole('button', {name: /Save and Proceed/}).click();
  await page.locator('#id_reel_duration[aria-invalid="true"]').waitFor();
  await page.getByText('This field is required.', {exact: true}).waitFor();
  assert.equal(await page.locator('#id_reel_duration').evaluate(field => field === document.activeElement), true);
  assert.equal(await page.getByLabel('Project name').inputValue(), 'Recovery browser brief');
  assert.equal(await page.getByLabel('Add wording or on-screen text').isChecked(), true);
  assert.equal(await page.getByLabel('Font selection').inputValue(), 'font_inspiration');
  assert.equal(await page.locator('[data-wording-direction]').isVisible(), true);
  assert.equal(await page.locator('[data-font-inspiration]').isVisible(), true);
  assert.equal(await page.getByLabel('Inspiration link').inputValue(), 'https://example.com/reference');
  assert.equal(await page.getByLabel('Music preference').inputValue(), 'provide');
  assert.equal(await page.getByLabel('Song Name or Link').inputValue(), 'Keep this song choice after validation.');
  assert.equal(await page.getByLabel('Revisions needed').inputValue(), '3-4');
  assert.equal(await page.locator('#upload-clips').evaluate(input => input.files.length), 1);
  assert.equal(await page.locator('#upload-inspiration').evaluate(input => input.files.length), 3);
  assert.equal(await page.locator('#brief-font-inspiration').evaluate(input => input.files.length), 1);
  // The retention assertions above cover all upload controls. Keep the
  // interrupted-upload portion focused on its original three-reference queue.
  await page.locator('#upload-clips').setInputFiles([]);
  await page.locator('#brief-font-inspiration').setInputFiles([]);
  await page.getByLabel('Reel duration').selectOption('30_50');

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
  await page.waitForURL(/\/orders\/[a-f0-9-]+\/$/, {timeout: 90000});
  const projectId = page.url().match(/\/orders\/([a-f0-9-]+)\//i)?.[1];
  assert(projectId, 'Saved project ID is missing after upload recovery.');

  const beforeRemoval = await page.evaluate(async id => {
    const response = await fetch(`/api/projects/${id}/`);
    return {status: response.status, body: await response.json()};
  }, projectId);
  assert.equal(beforeRemoval.status, 200, JSON.stringify(beforeRemoval.body));
  const references = beforeRemoval.body.files.filter(file => file.category === 'reference');
  assert.equal(references.length, 3);
  assert(!references.some(file => file.filename === 'recovery-reference-4.jpg'));
  await page.goto(`${fixture.base}/client/projects/${projectId}/edit/`);
  await page.getByText('recovery-reference-1.jpg', {exact: true}).waitFor({timeout: 60000});
  const removalResponse = page.waitForResponse(response => (
    response.request().method() === 'POST' && response.url().includes('/remove/')
  ));
  await page.getByRole('button', {name: 'Remove recovery-reference-1.jpg'}).click();
  const removed = await removalResponse;
  assert.equal(removed.status(), 200, await removed.text());
  await page.getByText('recovery-reference-1.jpg removed from this brief.').waitFor({timeout: 10000});
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
