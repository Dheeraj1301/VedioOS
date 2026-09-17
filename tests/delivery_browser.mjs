import { chromium } from '@playwright/test';
import { createHash } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';

const f=JSON.parse(process.env.DELIVERY_BROWSER_FIXTURE);
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
  await page.waitForURL(/\/(editor|client)\/$/);
}
async function logout() {
  await page.getByRole('button',{name:'Log out'}).filter({visible:true}).click();
  await page.waitForURL(`${f.base}/`);
}
async function post(path,data) {
  const csrf=await page.locator('[name=csrfmiddlewaretoken]').first().inputValue();
  return page.request.post(f.base+path,{data,headers:{'X-CSRFToken':csrf}});
}
async function upload(project,number) {
  const bytes=Buffer.concat([Buffer.from('synthetic edited output '+number),Buffer.from(Array.from({length:2048},(_,i)=>i%256))]);
  const r=await post(`/api/projects/${project}/uploads/`,{filename:`version-${number}.mp4`,content_type:'video/mp4',category:'draft',size_bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});
  assert.equal(r.status(),201,await r.text());
  const reserved=await r.json();
  const put=await page.request.put(reserved.upload.url,{data:bytes,headers:reserved.upload.headers});
  assert.ok([200,201].includes(put.status()));
  assert.equal((await post(`/api/files/${reserved.file_id}/complete/`,{})).status(),200);
  await page.reload();
  await page.getByLabel('Verified upload').selectOption(reserved.file_id);
  await page.getByLabel('Note to client').fill(`Synthetic version ${number}`);
  await page.getByRole('button',{name:'Submit for review'}).click();
  await page.getByText('Project updated.',{exact:true}).waitFor();
  return {id:reserved.file_id,bytes};
}
async function download(file) {
  const r=await post(`/api/files/${file.id}/download/`,{});
  assert.equal(r.status(),200);
  const result=await page.request.get((await r.json()).url);
  assert.equal(result.status(),200);
  assert.deepEqual(await result.body(),file.bytes);
}
try {
  await mkdir('.runtime/screenshots',{recursive:true});
  await login(f.editors[0]);
  await page.goto(`${f.base}/editor/projects/${f.projects[0]}/`);
  await page.getByRole('button',{name:'Start editing / revision'}).click();
  const first=await upload(f.projects[0],1);
  await logout();
  await login(f.buyer);
  await page.goto(`${f.base}/client/projects/${f.projects[0]}/`);
  await download(first);
  await page.getByLabel('Requested changes').fill('00:03 shorten the opening.');
  await page.getByRole('button',{name:'Request revision',exact:true}).click();
  await page.getByText('Revision requested',{exact:true}).waitFor();
  await logout();
  await login(f.editors[0]);
  await page.goto(`${f.base}/editor/revisions/`);
  await page.getByRole('link',{name:'Synthetic assignment',exact:false}).first().click();
  await page.getByRole('button',{name:'Start editing / revision'}).click();
  const second=await upload(f.projects[0],2);
  await logout();
  await login(f.buyer);
  await page.goto(`${f.base}/client/projects/${f.projects[0]}/`);
  await page.getByLabel('I accept version 2').check();
  await page.getByRole('button',{name:'Accept version 2',exact:true}).click();
  await page.getByText('Completed',{exact:true}).waitFor();
  await download(first); await download(second);
  await page.screenshot({path:'.runtime/screenshots/phase5-accepted-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.screenshot({path:'.runtime/screenshots/phase5-accepted-mobile.png',fullPage:true});
  await logout();
  await login(f.editors[1]);
  await page.goto(`${f.base}/editor/projects/${f.projects[1]}/`);
  await page.getByRole('button',{name:'Start editing / revision'}).click();
  const draft=await upload(f.projects[1],1);
  await logout(); await login(f.buyer);
  await page.goto(`${f.base}/client/projects/${f.projects[1]}/`);
  await page.getByLabel('I accept version 1').check();
  await page.getByRole('button',{name:'Accept version 1',exact:true}).click();
  await page.getByText('Completed',{exact:true}).waitFor(); await download(draft);
  assert.deepEqual(errors,[]);
  console.log('PASS: real Edge review/revision/new version/acceptance, first-draft acceptance, private S3 byte integrity, desktop/mobile.');
} finally {await browser.close();}
