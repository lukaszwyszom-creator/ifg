/**
 * GWO-IFG-0027 — production UI verify via SSH SOCKS (LocalForward often blocked on NAS).
 *
 *   node frontend-react/scripts/verify-buyer-popup-prod.mjs
 */
import { spawn } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';
import { chromium } from 'playwright';

const SOCKS_PORT = Number(process.env.IFG_SOCKS_PORT || 18028);
const SSH_PORT = process.env.DS723_PORT || '32122';
const SSH_HOST = process.env.DS723_HOST || 'ds723';
const SSH_USER = process.env.DS723_USER || 'zdalny_admin';
const REMOTE_ENV = '/volume1/docker/ifg_v2/ifg_standalone/.env.production';
const APP = 'http://127.0.0.1:8000';

function startSocks() {
  return spawn(
    'ssh',
    [
      '-p', SSH_PORT,
      '-o', 'ExitOnForwardFailure=yes',
      '-o', 'ServerAliveInterval=30',
      '-N',
      '-D', String(SOCKS_PORT),
      `${SSH_USER}@${SSH_HOST}`,
    ],
    { stdio: ['ignore', 'pipe', 'pipe'] },
  );
}

async function remoteCreds() {
  return await new Promise((resolve, reject) => {
    const child = spawn(
      'ssh',
      [
        '-p', SSH_PORT,
        `${SSH_USER}@${SSH_HOST}`,
        `python3 - <<'PY'
from pathlib import Path
vals = {}
for line in Path(${JSON.stringify(REMOTE_ENV)}).read_text().splitlines():
    line=line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k,v=line.split("=",1)
    vals[k]=v.strip().strip('"').strip("'")
print(vals.get("INITIAL_ADMIN_USERNAME",""))
print(vals.get("INITIAL_ADMIN_PASSWORD",""))
PY`,
      ],
      { stdio: ['ignore', 'pipe', 'pipe'] },
    );
    let out = '';
    let err = '';
    child.stdout.on('data', (d) => { out += d.toString(); });
    child.stderr.on('data', (d) => { err += d.toString(); });
    child.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`creds ssh failed: ${err || code}`));
        return;
      }
      const [username, password] = out.trim().split('\n');
      if (!username || !password) {
        reject(new Error('missing INITIAL_ADMIN credentials'));
        return;
      }
      resolve({ username, password });
    });
  });
}

async function main() {
  const socks = startSocks();
  let socksErr = '';
  socks.stderr.on('data', (d) => { socksErr += d.toString(); });
  await sleep(1200);

  try {
    const { username, password } = await remoteCreds();

    const browser = await chromium.launch({
      headless: true,
      proxy: { server: `socks5://${'127.0.0.1'}:${SOCKS_PORT}` },
    });
    const context = await browser.newContext({
      ignoreHTTPSErrors: true,
      proxy: { server: `socks5://127.0.0.1:${SOCKS_PORT}` },
    });
    const page = await context.newPage();

    // Health through browser fetch via page.evaluate after goto won't work first.
    // Login via page.request (uses context proxy).
    const loginRes = await context.request.post(`${APP}/api/v1/auth/login`, {
      data: { username, password },
    });
    if (!loginRes.ok()) {
      throw new Error(`login HTTP ${loginRes.status()}`);
    }
    const loginData = await loginRes.json();
    if (!loginData.access_token) throw new Error('login missing access_token');

    await page.addInitScript((authToken) => {
      localStorage.setItem(
        'faktura-auth',
        JSON.stringify({
          state: { token: authToken, user: { username: 'prod-verify' } },
          version: 0,
        }),
      );
    }, loginData.access_token);

    await page.goto(`${APP}/ui/invoices`, { waitUntil: 'networkidle', timeout: 90000 });
    await sleep(1500);

    if (page.url().includes('/login')) {
      throw new Error('redirected to login — auth failed');
    }

    // Confirm production bundle is the new one
    const scripts = await page.locator('script[src*="assets/index-"]').evaluateAll((els) =>
      els.map((e) => e.getAttribute('src')));
    if (!scripts.some((s) => s && s.includes('index-UQImflzm.js'))) {
      throw new Error(`unexpected bundle scripts: ${JSON.stringify(scripts)}`);
    }

    const trigger = page.locator('[data-buyer-hover-trigger="true"]').first();
    await trigger.waitFor({ state: 'visible', timeout: 45000 });
    const buyerName = (await trigger.innerText()).trim();
    if (!buyerName || buyerName === '—') {
      throw new Error('empty buyer trigger text');
    }

    const grid = trigger.locator('xpath=ancestor::div[contains(@class,"invoiceGrid")][1]');
    const numberValue = grid.locator('[class*="invoiceCellNumber"] [class*="value"]').first();
    await numberValue.waitFor({ state: 'visible', timeout: 10000 });
    await numberValue.hover();
    await sleep(350);
    const numberTitle = await numberValue.getAttribute('title');
    if (numberTitle && /Źródło numeru|number_local|numberSource|backend:/i.test(numberTitle)) {
      throw new Error(`technical tooltip on number: ${numberTitle}`);
    }
    if ((await page.locator('[data-buyer-popup="true"]').count()) !== 0) {
      throw new Error('popup opened on invoice number hover');
    }

    await trigger.hover();
    const popup = page.locator('[data-buyer-popup="true"]');
    await popup.waitFor({ state: 'visible', timeout: 5000 });
    const popupText = await popup.innerText();
    const expectedName = buyerName.split('\n')[0].trim();
    if (!popupText.includes(expectedName)) {
      throw new Error(`popup name mismatch. trigger=${buyerName} popup=${popupText}`);
    }

    await popup.hover();
    await sleep(220);
    if ((await page.locator('[data-buyer-popup="true"]').count()) === 0) {
      throw new Error('popup flickered away when moving onto it');
    }

    await page.mouse.move(0, 0);
    await sleep(320);
    if ((await page.locator('[data-buyer-popup="true"]').count()) !== 0) {
      throw new Error('popup did not close after leave');
    }

    await browser.close();
    console.log('BUYER_POPUP_PROD_VERIFY=PASS');
    console.log(`BUNDLE=index-UQImflzm.js`);
    console.log(`BUYER_NAME_CHECKED_LEN=${expectedName.length}`);
  } catch (err) {
    if (socksErr) console.error('SOCKS stderr:', socksErr.slice(-2000));
    throw err;
  } finally {
    socks.kill('SIGTERM');
  }
}

main().catch((err) => {
  console.error('BUYER_POPUP_PROD_VERIFY=FAIL', err.message || err);
  process.exit(1);
});
