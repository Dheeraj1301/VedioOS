import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';

const f=JSON.parse(process.env.EARNING_BROWSER_FIXTURE);
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('response',r=>{if(r.status()>=500) errors.push(`HTTP ${r.status()}`);});
async function login(email) {
  await page.goto(`${f.base}/login/`);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(f.password);
  await page.getByRole('button',{name:'Log in'}).click();
  await page.waitForURL(/\/(admin|editor)\/$/);
}
async function logout() {
  await page.getByRole('button',{name:'Log out'}).filter({visible:true}).click();
  await page.waitForURL(`${f.base}/`);
}
try {
  await mkdir('.runtime/screenshots',{recursive:true});
  await login(f.editor);
  await page.goto(`${f.base}/editor/wallet/`);
  await page.getByText('Pending release').waitFor();
  assert.equal(await page.locator('.stats strong').nth(0).textContent(),'120');
  await logout(); await login(f.admin);
  await page.goto(`${f.base}/admin/payouts/`);
  await page.getByRole('button',{name:'Release agreed coins'}).click();
  await page.getByText('Earning or redemption updated.').waitFor();
  await logout(); await login(f.editor);
  await page.goto(`${f.base}/editor/wallet/`);
  assert.equal(await page.locator('.stats strong').nth(2).textContent(),'120');
  await page.getByLabel('Whole coins to redeem').fill('75');
  await page.getByRole('button',{name:'Reserve coins'}).click();
  assert.equal(await page.locator('.stats strong').nth(2).textContent(),'45');
  await logout(); await login(f.admin); await page.goto(`${f.base}/admin/payouts/`);
  await page.getByRole('button',{name:'Simulate failed payout'}).click();
  await logout(); await login(f.editor); await page.goto(`${f.base}/editor/wallet/`);
  assert.equal(await page.locator('.stats strong').nth(2).textContent(),'120');
  await page.getByLabel('Whole coins to redeem').fill('75');
  await page.getByRole('button',{name:'Reserve coins'}).click();
  await logout(); await login(f.admin); await page.goto(`${f.base}/admin/payouts/`);
  await page.getByLabel('Sandbox reference').fill('synthetic-browser-payout-1');
  await page.getByRole('button',{name:'Simulate paid'}).click();
  await logout(); await login(f.editor); await page.goto(`${f.base}/editor/wallet/`);
  assert.equal(await page.locator('.stats strong').nth(2).textContent(),'45');
  assert.equal(await page.locator('.stats strong').nth(3).textContent(),'75');
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.screenshot({path:'.runtime/screenshots/phase6-wallet-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: Edge editor wallet, admin release, reserve, failed payout release, successful sandbox payout and mobile layout.');
} finally {await browser.close();}
