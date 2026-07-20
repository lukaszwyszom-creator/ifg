/**
 * GWO-IFG-0027 — weryfikacja rzeczywistego hover (Playwright).
 * Uruchomienie:
 *   node frontend-react/scripts/verify-buyer-popup-hover.mjs
 */
import { spawn } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dir, '..');
const PORT = Number(process.env.BUYER_POPUP_SMOKE_PORT || 3017);
const BASE = `http://127.0.0.1:${PORT}`;
const SMOKE_URL = `${BASE}/ui/buyer-popup-smoke.html`;
const SMOKE_URL_FALLBACK = `${BASE}/buyer-popup-smoke.html`;

function startVite() {
  return spawn(
    'npx',
    ['vite', '--host', '127.0.0.1', '--port', String(PORT), '--strictPort'],
    {
      cwd: frontendRoot,
      env: {
        ...process.env,
        PORT: String(PORT),
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
}

async function waitForServer(urls, timeoutMs = 45000) {
  const list = Array.isArray(urls) ? urls : [urls];
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    for (const url of list) {
      try {
        const res = await fetch(url);
        if (res.ok || res.status === 304) return url;
      } catch {
        // retry
      }
    }
    await sleep(400);
  }
  throw new Error(`Vite smoke server not ready: ${list.join(' | ')}`);
}

async function main() {
  const vite = startVite();
  let logs = '';
  vite.stdout.on('data', (d) => {
    logs += d.toString();
  });
  vite.stderr.on('data', (d) => {
    logs += d.toString();
  });

  try {
    const smokeUrl = await waitForServer([SMOKE_URL, SMOKE_URL_FALLBACK]);
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    page.on('pageerror', (err) => {
      console.error('Page error:', err.message);
    });
    await page.goto(smokeUrl, { waitUntil: 'networkidle' });

    const numberSpan = page.getByText('01/07/2026', { exact: true });
    await numberSpan.waitFor({ state: 'visible' });

    await numberSpan.hover();
    await sleep(250);
    const numberTitle = await numberSpan.getAttribute('title');
    if (numberTitle && /Źródło numeru|number_local|numberSource/i.test(numberTitle)) {
      throw new Error(`Techniczny tooltip na numerze: ${numberTitle}`);
    }

    const popupBefore = await page.locator('[data-buyer-popup="true"]').count();
    if (popupBefore !== 0) {
      throw new Error('Popup widoczny przed hoverem nabywcy');
    }

    const trigger = page.locator('[data-buyer-hover-trigger="true"]');
    await trigger.waitFor({ state: 'visible' });
    await trigger.hover();
    await page.locator('[data-buyer-popup="true"]').waitFor({ state: 'visible', timeout: 3000 });
    const popupText = await page.locator('[data-buyer-popup="true"]').innerText();
    if (!popupText.includes('ACME Kontrahent Smoke')) {
      throw new Error(`Popup bez właściwej nazwy nabywcy: ${popupText}`);
    }
    if (!popupText.includes('+48 500 100 200') || !popupText.includes('kontakt@acme-smoke.example')) {
      throw new Error(`Popup bez kontaktu: ${popupText}`);
    }
    if (popupText.includes('5250000999')) {
      throw new Error('Popup nie powinien pokazywać NIP');
    }

    await page.locator('[data-buyer-popup="true"]').hover();
    await sleep(200);
    if ((await page.locator('[data-buyer-popup="true"]').count()) === 0) {
      throw new Error('Popup zniknął przy przejściu kursora na popup (migotanie)');
    }

    await page.mouse.move(0, 0);
    await sleep(250);
    if ((await page.locator('[data-buyer-popup="true"]').count()) !== 0) {
      throw new Error('Popup nie zamknął się po opuszczeniu obszaru');
    }

    await browser.close();
    console.log('BUYER_POPUP_HOVER_VERIFY=PASS');
  } catch (err) {
    console.error('Vite logs:\n', logs.slice(-4000));
    throw err;
  } finally {
    vite.kill('SIGTERM');
  }
}

main().catch((err) => {
  console.error('BUYER_POPUP_HOVER_VERIFY=FAIL', err);
  process.exit(1);
});
