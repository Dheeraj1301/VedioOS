import { chromium } from '@playwright/test';
import { createHmac, randomUUID } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';

const fixture = JSON.parse(process.env.COMMERCE_BROWSER_FIXTURE);
const browser = await chromium.launch({headless: true, channel: 'msedge'});
const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {if (response.status() >= 500) errors.push(`HTTP ${response.status()}: ${response.url()}`);});
const base = fixture.base;
async function login(email) {
  await page.goto(`${base}/login/`);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', {exact: true}).fill(fixture.password);
  await page.getByRole('button', {name: 'Log in'}).click();
  await page.waitForURL(/\/(admin|client)\/$/);
}
async function logout() {
  await page.getByRole('button', {name: 'Log out'}).filter({visible: true}).click();
  await page.waitForURL(`${base}/`);
}
async function save() {
  await page.getByRole('button', {name: 'Save configuration'}).click();
  await page.waitForURL(`${base}/admin/pricing/`);
}
try {
  await mkdir('.runtime/screenshots', {recursive: true});
  await login('browser-admin@example.test');
  await page.goto(`${base}/admin/pricing/`);
  assert.equal(await page.locator('.catalog-grid article').count(), 3);
  await page.getByRole('link', {name: 'Edit commercial terms'}).click();
  await page.locator('#id_currency').selectOption('INR');
  for (const [key,value] of Object.entries({custom_base_minor:'10000',custom_revision_limit:'2',custom_delivery_hours:'24',custom_duration_limit_seconds:'60',custom_priority:'1',terms:'TEST service agreement',delivery_terms:'TEST timing pending owner decision',refund_terms:'TEST refund policy',tax_terms:'TEST taxes included'})) {
    await page.locator(`#id_${key}`).fill(value);
  }
  await page.locator('#id_quotes_enabled').check();
  await save();
  await page.getByRole('link', {name: 'Configure plan 1'}).click();
  for (const [key,value] of Object.entries({name:'Synthetic starter',price_minor:'25000',features:'Cuts\nCaptions',revision_limit:'2',delivery_hours:'24',duration_limit_seconds:'60',priority:'1'})) {
    await page.locator(`#id_${key}`).fill(value);
  }
  await page.locator('#id_currency').selectOption('INR');
  await page.locator('#id_active').check();
  await save();
  await page.getByRole('link', {name: 'Add service'}).click();
  await page.locator('#id_name').fill('Synthetic captions');
  await page.locator('#id_price_minor').fill('1500');
  await page.locator('#id_currency').selectOption('INR');
  await page.locator('#id_active').check();
  await save();
  await page.screenshot({path:'.runtime/screenshots/phase3-admin-catalog.png',fullPage:true});
  await logout();
  await login('browser-buyer@example.test');
  await page.goto(`${base}/client/projects/${fixture.project}/quote/`);
  await page.locator('#id_kind').selectOption('custom');
  await page.getByLabel('Synthetic captions', {exact:true}).check();
  await page.locator('#id_scope_confirmed').check();
  await page.getByRole('button', {name:'Calculate my quote'}).click();
  await page.getByRole('heading', {name:'Your quote.'}).waitFor();
  assert.match(await page.locator('main').innerText(), /INR 115\.00/);
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth), true);
  await page.screenshot({path:'.runtime/screenshots/phase3-mobile-quote.png',fullPage:true});
  await page.getByLabel('I accept this price').check();
  await page.getByRole('button', {name:'Accept quote'}).click();
  await page.getByRole('heading', {name:'Order summary.'}).waitFor();
  await page.getByRole('button', {name:'Start / retry sandbox payment'}).click();
  await page.getByText('sandbox · pending').waitFor();
  // The trusted test gateway signs the event outside the browser. No client-side success flag.
  const gateway = await fetch(`${base}/__test_gateway_fixture__/`);
  assert.equal(gateway.status, 404); // There is deliberately no payment-secret or fixture endpoint.
  // Read payment identifiers from the protected summary's data attributes; these are not credentials.
  const info = await page.locator('[data-payment-reference]').first().evaluate(el=>({...el.dataset}));
  const body = JSON.stringify({event_id:randomUUID(), reference:info.paymentReference, order_id:info.orderId, amount_minor:11500, currency:'INR', status:'confirmed'});
  const stamp = Math.floor(Date.now()/1000).toString();
  const signature = `${stamp}.${createHmac('sha256',fixture.secret).update(`${stamp}.${body}`).digest('hex')}`;
  for (let n=0;n<2;n++) {
    const response = await fetch(`${base}/api/payments/sandbox/webhook/`,{method:'POST',headers:{'Content-Type':'application/json','X-Sandbox-Signature':signature},body});
    assert.equal(response.status,200);
  }
  await page.reload();
  await page.getByRole('link', {name:'View receipt'}).click();
  await page.getByRole('heading', {name:'TEST RECEIPT — no money received'}).waitFor();
  await page.screenshot({path:'.runtime/screenshots/phase3-receipt.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: admin catalog forms → custom quote → mobile acceptance → signed gateway → duplicate callback → protected receipt. No page errors or mobile overflow.');
} finally {await browser.close();}
