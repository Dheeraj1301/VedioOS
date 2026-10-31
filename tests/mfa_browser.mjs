import { createHmac } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';

// Answers the administrator/editor code step like an authenticator app would. The setup key
// is read from the page on first sign-in and kept in ignored .runtime for later suites.
const store = '.runtime/browser-mfa-keys.json';
const saved = existsSync(store) ? JSON.parse(readFileSync(store, 'utf8')) : {keys: {}, steps: {}};
const keys = new Map(Object.entries(saved.keys));
const usedSteps = new Map(Object.entries(saved.steps));
const persist = () => writeFileSync(store, JSON.stringify({keys: Object.fromEntries(keys), steps: Object.fromEntries(usedSteps)}));

function code(secret, step) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  const bits = [...secret].map(c => alphabet.indexOf(c).toString(2).padStart(5, '0')).join('');
  const key = Buffer.from(bits.match(/.{8}/g).map(byte => parseInt(byte, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac('sha1', key).update(counter).digest();
  const offset = digest[digest.length - 1] & 15;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1e6).padStart(6, '0');
}

export async function passCodeStep(page, account) {
  await page.waitForURL(url => !['/login/', '/editor/signin/'].includes(url.pathname), {timeout: 10000}).catch(() => {});
  if (new URL(page.url()).pathname !== '/login/verify/') return;
  const setupKey = page.locator('code');
  if (await setupKey.count()) keys.set(account, (await setupKey.textContent()).replace(/\s/g, ''));
  const secret = keys.get(account);
  if (!secret) throw new Error(`No authenticator key is known for ${account}.`);
  let step = Math.floor(Date.now() / 30000);
  if (step <= (usedSteps.get(account) ?? -1)) {
    await page.waitForTimeout((step + 1) * 30000 - Date.now() + 250);
    step += 1;
  }
  usedSteps.set(account, step);
  persist();
  await page.getByLabel('Verification code', {exact: true}).fill(code(secret, step));
  await Promise.all([page.waitForNavigation(), page.getByRole('button', {name: 'Verify and continue'}).click()]);
}
