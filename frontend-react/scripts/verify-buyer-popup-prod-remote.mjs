/**
 * GWO-IFG-0028 — production UI verify ON DS723 (Docker --network host).
 * Sprawdza popup Nabywcy i Sprzedawcy z tytułem „Nazwa, Miejscowość”.
 */
import { readFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { chromium } from 'playwright';

const APP = process.env.IFG_APP_URL || 'http://127.0.0.1:8000';
const ENV_FILE = process.env.IFG_ENV_FILE || '/work/.env.production';
const EXPECTED_JS = process.env.IFG_EXPECTED_JS || '';

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
    if (document.querySelector('[data-contractor-hover-trigger="true"], [data-buyer-hover-trigger="true"]')) {
      return true;
    }
    if (document.querySelector('[class*="invoiceCellNumber"]')) return true;
    if (document.querySelector('.spinner')) return false;
    return false;
  }, { timeout: 60000 });
}

function triggerLocator(page) {
  return page.locator('[data-contractor-hover-trigger="true"], [data-buyer-hover-trigger="true"]');
}

function popupLocator(page) {
  return page.locator('[data-contractor-popup="true"], [data-buyer-popup="true"]');
}

async function findTriggerViaMonthPills(page) {
  if ((await triggerLocator(page).count()) > 0) return triggerLocator(page).first();
  const pills = page.locator('button').filter({ hasText: /^(sty|lut|mar|kwi|maj|cze|lip|sie|wrz|paź|lis|gru)/i });
  const pillCount = await pills.count();
  for (let i = 0; i < pillCount; i += 1) {
    await pills.nth(i).click();
    await sleep(1200);
    await waitForInvoicesOrEmpty(page);
    if ((await triggerLocator(page).count()) > 0) return triggerLocator(page).first();
  }
  return null;
}

/**
 * @returns {{ titleLine: string, city: string, cityMissing: boolean }}
 */
function assertNameCityTitle(popupText, contractorName, role, { requireCity = true } = {}) {
  const titleLine = (popupText.split('\n')[0] || '').trim();
  if (!titleLine.startsWith(contractorName)) {
    throw new Error(`${role}: popup title missing contractor name. title=${titleLine}`);
  }
  const afterName = titleLine.slice(contractorName.length);
  if (!afterName.startsWith(',')) {
    throw new Error(`${role}: expected „Nazwa, Miejscowość”, got: ${titleLine}`);
  }
  const city = afterName.slice(1).trim();
  const cityMissing = !city || city === 'undefined' || city === 'null';
  if (requireCity && cityMissing) {
    throw new Error(
      `${role}: DATA_ERROR — brak miejscowości (city) w popupu dla „${contractorName}” (title=${titleLine})`,
    );
  }
  if (!cityMissing && /ul\.|al\.|pl\.|\d{2}-\d{3}|wojew|Polska|Poland/i.test(city)) {
    throw new Error(`${role}: title zawiera więcej niż miejscowość: ${titleLine}`);
  }
  return { titleLine, city, cityMissing };
}

async function verifyContractorPopup(page, trigger, role, options = {}) {
  const contractorName = (await trigger.innerText()).trim();
  if (!contractorName || contractorName === '—') {
    throw new Error(`${role}: empty contractor trigger text`);
  }

  await trigger.hover();
  const popup = popupLocator(page);
  await popup.waitFor({ state: 'visible', timeout: 5000 });
  const popupText = await popup.innerText();
  const result = assertNameCityTitle(popupText, contractorName, role, options);

  await popup.hover();
  await sleep(220);
  if ((await popupLocator(page).count()) === 0) {
    throw new Error(`${role}: popup flickered away when moving onto it`);
  }

  await page.mouse.move(0, 0);
  await sleep(320);
  if ((await popupLocator(page).count()) !== 0) {
    throw new Error(`${role}: popup did not close after leave`);
  }

  return { contractorName, ...result };
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
  if (EXPECTED_JS && !scripts.some((s) => s && s.includes(EXPECTED_JS))) {
    throw new Error(`unexpected bundle scripts: ${JSON.stringify(scripts)}`);
  }
  const activeJs = scripts.find((s) => s && s.includes('index-')) || scripts[0] || '';

  await waitForInvoicesOrEmpty(page);
  let buyerTrigger = await findTriggerViaMonthPills(page);
  if (!buyerTrigger) {
    await page.goto(`${APP}/ui/dashboard`, { waitUntil: 'networkidle', timeout: 90000 });
    await sleep(800);
    const saleTab = page.getByRole('button', { name: /Faktury sprzedaży/i });
    if ((await saleTab.count()) > 0) {
      await saleTab.first().click();
      await sleep(1500);
      await waitForInvoicesOrEmpty(page);
    }
    buyerTrigger = await findTriggerViaMonthPills(page);
  }
  if (!buyerTrigger) {
    throw new Error('no buyer (sale) hover trigger found');
  }

  const buyer = await verifyContractorPopup(page, buyerTrigger, 'Nabywca', { requireCity: true });

  // Sprzedawca — zakładka zakupów w Zestawieniach
  await page.goto(`${APP}/ui/dashboard`, { waitUntil: 'networkidle', timeout: 90000 });
  await sleep(800);
  const purchaseTab = page.getByRole('button', { name: /Faktury zakupowe/i });
  if ((await purchaseTab.count()) > 0) {
    await purchaseTab.first().click();
  } else {
    const tabs = page.locator('button').filter({ hasText: /zakup/i });
    if ((await tabs.count()) === 0) throw new Error('purchase tab not found on /ui/dashboard');
    await tabs.first().click();
  }
  await sleep(1500);
  await waitForInvoicesOrEmpty(page);
  let sellerTrigger = await findTriggerViaMonthPills(page);
  if (!sellerTrigger && (await triggerLocator(page).count()) > 0) {
    sellerTrigger = triggerLocator(page).first();
  }
  if (!sellerTrigger) {
    throw new Error('no seller (purchase) hover trigger found');
  }
  // requireCity=false: produkcja ma puste seller_snapshot.city (błąd danych — bez fallbacku UI)
  const seller = await verifyContractorPopup(page, sellerTrigger, 'Sprzedawca', {
    requireCity: false,
  });

  await browser.close();
  console.log('BUYER_POPUP_PROD_VERIFY=PASS');
  console.log('SELLER_POPUP_HOVER_VERIFY=PASS');
  console.log(`BUYER_CITY_DISPLAY=${buyer.cityMissing ? 'FAIL' : 'PASS'}`);
  console.log(`SELLER_CITY_DATA_ERROR=${seller.cityMissing ? 'YES' : 'NO'}`);
  console.log(`BUNDLE=${activeJs}`);
  console.log(`BUYER_TITLE=${buyer.titleLine}`);
  console.log(`SELLER_TITLE=${seller.titleLine}`);
  if (seller.cityMissing) {
    console.log(
      'NOTE: seller_snapshot.city empty on sampled purchase invoices — UI shows „Nazwa,” without locality; no UI fallback per GWO.',
    );
  }
}

main().catch((err) => {
  console.error('BUYER_POPUP_PROD_VERIFY=FAIL', err.message || err);
  process.exit(1);
});
