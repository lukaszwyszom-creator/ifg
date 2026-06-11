import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));

function read(relativePath) {
  return readFileSync(join(__dir, relativePath), 'utf-8');
}

test('ksef API: runPurchaseSync preferuje syncPurchaseInvoices + polling job status', () => {
  const source = read('ksef.js');
  assert.match(source, /async function runPurchaseSync\(/);
  assert.match(source, /await syncPurchaseInvoices\(nip, dateFrom, dateTo\)/);
  assert.match(source, /pollPurchaseSyncJob\(jobId, getSyncPurchaseJobStatus/);
  assert.match(source, /sync-purchase\/jobs/);
  assert.match(source, /ksefApi\.syncPurchaseInvoices/);
  assert.match(source, /ksefApi\.getSyncPurchaseJobStatus/);
});

test('ksef API: fallback sync tylko przy HTTP 404 na enqueue', () => {
  const source = read('ksef.js');
  assert.match(source, /err\.response\?\.status === 404/);
  assert.match(source, /syncPurchasesNowFallback/);
  assert.match(source, /404 na job API/);
  assert.match(source, /timeout: 600000/);
  assert.doesNotMatch(source, /await pollPurchaseSyncJob[\s\S]*syncPurchasesNowFallback/);
});

test('UI Odśwież KSeF: używa runPurchaseSync, bez syncPurchasesNow', () => {
  const topbar = read('../components/layout/KSeFTopbarInfo.jsx');
  const sessionBar = read('../components/dashboard/KSeFSessionBar.jsx');
  assert.match(topbar, /ksefApi\.runPurchaseSync\(/);
  assert.doesNotMatch(topbar, /syncPurchasesNow/);
  assert.match(sessionBar, /ksefApi\.runPurchaseSync\(/);
  assert.doesNotMatch(sessionBar, /syncPurchasesNow/);
});

test('normalizePurchaseSyncCounts: mapuje pola sync v2 i job result', () => {
  const source = read('ksef.js');
  assert.match(source, /raw\.saved \?\? raw\.created/);
  assert.match(source, /raw\.received \?\? raw\.ksef_returned/);
  assert.match(source, /raw\.skipped_parse \?\? raw\.errors/);
});
