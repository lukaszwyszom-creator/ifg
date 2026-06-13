import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const componentsDir = join(__dir, '../components');

function read(relativePath) {
  return readFileSync(join(__dir, relativePath), 'utf-8');
}

function listJsxFiles(dir) {
  const files = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      files.push(...listJsxFiles(full));
    } else if (entry.endsWith('.jsx')) {
      files.push(full);
    }
  }
  return files;
}

test('ksef API: runPurchaseSync preferuje syncPurchaseInvoices + polling job status', () => {
  const source = read('ksef.js');
  assert.match(source, /async function runPurchaseSync\(/);
  assert.match(source, /await syncPurchaseInvoices\(nip, dateFrom, dateTo\)/);
  assert.match(source, /pollPurchaseSyncJob\(jobId, getSyncPurchaseJobStatus/);
  assert.match(source, /sync-purchase\/jobs/);
  assert.match(source, /ksefApi\.syncPurchaseInvoices/);
  assert.match(source, /ksefApi\.getSyncPurchaseJobStatus/);
  assert.match(source, /console\.info\('\[ksef-purchase-sync\]'/);
  assert.match(source, /KSEF_UI_TRIGGER_PURCHASE_SYNC/);
  assert.match(source, /export function formatPurchaseSyncError/);
});

test('ksef API: fallback sync tylko przy HTTP 404 na enqueue', () => {
  const source = read('ksef.js');
  assert.match(source, /err\.response\?\.status === 404/);
  assert.match(source, /syncPurchasesNowFallback/);
  assert.match(source, /404 na job API/);
  assert.match(source, /timeout: 600000/);
  assert.doesNotMatch(source, /await pollPurchaseSyncJob[\s\S]*syncPurchasesNowFallback/);
});

test('ksef API: openSession dedupe + jednorazowy retry transient', () => {
  const source = read('ksef.js');
  assert.match(source, /async function openSessionOnce\(/);
  assert.match(source, /openSessionInFlightPromise/);
  assert.match(source, /isTransientOpenSessionError/);
  assert.match(source, /openSession: \(nip\) => openSessionOnce\(nip\)/);
});

test('KSeFConnectionTile: guard przed równoległym connect i obsługa 409', () => {
  const source = read('../components/layout/KSeFConnectionTile.jsx');
  assert.match(source, /actionInFlightRef/);
  assert.match(source, /ui_status === 'CONNECTING'/);
  assert.match(source, /error\?\.response\?\.status === 409/);
  assert.match(source, /getActiveSession\(nipToUse\)/);
});

test('UI Odśwież KSeF: używa runPurchaseSync, bez syncPurchasesNow we wszystkich komponentach', () => {
  const topbar = read('../components/layout/KSeFTopbarInfo.jsx');
  const sessionBar = read('../components/dashboard/KSeFSessionBar.jsx');
  assert.match(topbar, /ksefApi\.runPurchaseSync\(/);
  assert.match(topbar, /Uruchamiam async sync/);
  assert.match(sessionBar, /ksefApi\.runPurchaseSync\(/);
  assert.match(sessionBar, /Uruchamiam async sync/);
  assert.match(topbar, /formatPurchaseSyncError/);
  assert.match(sessionBar, /formatPurchaseSyncError/);

  for (const jsxPath of listJsxFiles(componentsDir)) {
    const source = readFileSync(jsxPath, 'utf-8');
    assert.doesNotMatch(
      source,
      /syncPurchasesNow\s*\(/,
      `syncPurchasesNow( w ${jsxPath}`,
    );
  }
});

test('normalizePurchaseSyncCounts: mapuje pola sync v2 i job result', () => {
  const source = read('ksef.js');
  assert.match(source, /raw\.saved \?\? raw\.created/);
  assert.match(source, /raw\.received \?\? raw\.ksef_returned/);
  assert.match(source, /raw\.skipped_parse \?\? raw\.errors/);
});
