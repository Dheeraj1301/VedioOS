import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';

const fixture = JSON.parse(process.env.ASSIGNMENT_BROWSER_FIXTURE);
const browser = await chromium.launch({headless:true,channel:'msedge'});
const page = await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
page.on('response',r=>{if(r.status()>=500) errors.push(`HTTP ${r.status()}: ${r.url()}`);});
const base=fixture.base;
async function login(email) {
  await page.goto(`${base}/login/`);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(fixture.password);
  await page.getByRole('button',{name:'Log in'}).click();
  await page.waitForURL(/\/(admin|editor)\/$/);
}
async function logout() {
  await page.getByRole('button',{name:'Log out'}).filter({visible:true}).click();
  await page.waitForURL(`${base}/`);
}
try {
  await mkdir('.runtime/screenshots',{recursive:true});
  await login(fixture.admin);
  await page.goto(`${base}/admin/assignments/`);
  await page.getByRole('link',{name:'Configure allocation'}).click();
  await page.locator('#id_manual_enabled').check();
  await page.locator('#id_automatic_enabled').check();
  for(const [key,value] of Object.entries({matching:'exact',capacity_scope:'open_assignments',manual_pointer:'preserve',busy_strategy:'skip',roster_order:'joined',queue_order:'paid_at'})) await page.locator(`#id_${key}`).selectOption(value);
  await page.getByRole('button',{name:'Save settings'}).click();
  await page.waitForURL(`${base}/admin/assignments/`);
  await page.goto(`${base}/admin/editors/${fixture.editors[0].id}/operations/`);
  await page.locator('#id_workload_capacity').fill('1');
  await page.locator('#id_reason').fill('Synthetic capacity review');
  await page.getByRole('button',{name:'Save settings'}).click();
  await page.waitForURL(`${base}/admin/editors/`);
  await page.goto(`${base}/admin/assignments/${fixture.project}/`);
  await page.locator('#id_assessment-proficiency').selectOption('beginner');
  await page.locator('form').filter({has:page.locator('input[value="classify"]')}).getByLabel('Internal assessment').fill('Synthetic simple cuts require a beginner editor.');
  await page.getByRole('button',{name:'Save assessment'}).click();
  await page.getByText('Unassigned paid work is queued.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Assign next in rotation'}).click();
  await page.getByText('Current editor: Editor 1',{exact:false}).waitFor();
  await page.screenshot({path:'.runtime/screenshots/phase4-assigned.png',fullPage:true});
  await logout();
  await login(fixture.editors[0].email);
  await page.goto(`${base}/editor/projects/${fixture.project}/`);
  await page.getByRole('heading',{name:'Synthetic assignment browser project',exact:true}).waitFor();
  await logout();
  await login(fixture.admin);
  await page.goto(`${base}/admin/assignments/${fixture.project}/`);
  await page.locator('#id_manual-editor').selectOption(fixture.editors[1].id);
  await page.locator('form').filter({has:page.locator('input[value="manual"]')}).getByLabel('Reason',{exact:false}).fill('Synthetic reassignment for coverage');
  await page.getByRole('button',{name:'Save assignment'}).click();
  await page.getByText('Current editor: Editor 2',{exact:false}).waitFor();
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.screenshot({path:'.runtime/screenshots/phase4-mobile-reassignment.png',fullPage:true});
  await logout();
  await login(fixture.editors[0].email);
  const denied=await page.goto(`${base}/editor/projects/${fixture.project}/`);
  assert.equal(denied.status(),404);
  assert.deepEqual(errors,[]);
  console.log('PASS: configure policy/capacity → assess complexity → round robin → editor access → audited reassignment → former editor denied. Desktop/mobile checks passed.');
} finally {await browser.close();}
