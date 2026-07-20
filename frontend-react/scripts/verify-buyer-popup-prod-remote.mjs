/**
 * GWO-IFG-0027 — production UI verify ON DS723 (no SSH port forward).
 * Run inside Playwright Docker with --network host.
 */
import { readFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { chromium } from 'playwright';

const APP = process.env.IFG_APP_URL || 'http://127.0.0.1:8000';
const ENV_FILE = process.env.IFG_ENV_FILE || '/work/.env.production';
const EXPECTED_JS = process.env.IFG_EXPECTED_JS || 'index-UQImflzm.js';

function loadCreds() {
  const vals = {};
  for (const line of readFileSync(ENV_FILE, 'utf8').split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith('#') || !t.includes('=')) continue;
    const i = t.indexOf('=');
    const k = t.slice(0, i);
    let v = t.slice(i + 1).trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    vals[k] = v;
  }
  const username = vals.INITIAL_ADMIN_USERNAME;
  const password = vals.INITIAL_ADMIN_PASSWORD;
  if (!username || !password) throw new Error('missing INITIAL_ADMIN credentials');
  return { username, password };
}

async function waitForInvoicesOrEmpty(page) {
  await page.waitForFunction(() => {
    const text = document.body?.innerText || '';
    if (text.includes('Brak faktur')) return true;
    if (document.querySelector('[data-buyer-hover-trigger="true"]')) return true;
    if (document.querySelector('[class*="invoiceCellNumber"]')) return true;
    if (document.querySelector('.spinner')) return false;
    return false;
  }, { timeout: 60000 });
}

async function findBuyerTrigger(page) {
  const existing = page.locator('[data-buyer-hover-trigger="true"]');
  if ((await existing.count()) > 0) return existing.first();

  // Klikaj miesiące (od pierwszego z danymi / wszystkie pille)
  const pills = page.locator('button').filter({ hasText: /^(sty|lut|mar|kwi|maj|cze|lip|sie|wrz|paź|lis|gru)/i });
  const pillCount = await pills.count();
  for (let i = 0; i < pillCount; i += 1) {
    await pills.nth(i).click();
    await sleep(1200);
    await waitForInvoicesOrEmpty(page);
    if ((await page.locator('[data-buyer-hover-trigger="true"]').count()) > 0) {
      return page.locator('[data-buyer-hover-trigger="true"]').first();
    }
  }

  // Fallback: dashboard → Faktury sprzedaży (bez filtra miesiąca UI)
  await page.goto(`${APP}/ui/dashboard`, { waitUntil: 'networkidle', timeout: 90000 });
  await sleep(800);
  const tab = page.getByRole('button', { name: /Faktury sprzedaży/i }).or(
    page.getByText('Faktury sprzedaży', { exact: true }),
  );
  if ((await tab.count()) > 0) {
    await tab.first().click();
    await sleep(1500);
    await waitForInvoicesOrEmpty(page);
  }
  if ((await page.locator('[data-buyer-hover-trigger="true"]').count()) > 0) {
    return page.locator('[data-buyer-hover-trigger="true"]').first();
  }
  return null;
}

async function main() {
  const { username, password } = loadCreds();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const loginRes = await context.request.post(`${APP}/api/v1/auth/login`, {
    data: { username, password },
  });
  if (!loginRes.ok()) throw new Error(`login HTTP ${loginRes.status()}`);
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
  if (page.url().includes('/login')) throw new Error('redirected to login — auth failed');

  const scripts = await page.locator('script[src*="assets/index-"]').evaluateAll((els) =>
    els.map((e) => e.getAttribute('src')));
  if (!scripts.some((s) => s && s.includes(EXPECTED_JS))) {
    throw new Error(`unexpected bundle scripts: ${JSON.stringify(scripts)}`);
  }

  await waitForInvoicesOrEmpty(page);
  const trigger = await findBuyerTrigger(page);
  if (!trigger) {
    const snippet = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 700);
    throw new Error(`no buyer hover trigger found; page snippet: ${snippet}`);
  }

  const buyerName = (await trigger.innerText()).trim();
  if (!buyerName || buyerName === '—') throw new Error('empty buyer trigger text');

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
  console.log(`BUNDLE=${EXPECTED_JS}`);
  console.log(`BUYER_NAME_CHECKED_LEN=${expectedName.length}`);
}

main().catch((err) => {
  console.error('BUYER_POPUP_PROD_VERIFY=FAIL', err.message || err);
  process.exit(1);
});
