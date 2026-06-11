import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));

function read(relativePath) {
  return readFileSync(join(__dir, relativePath), 'utf-8');
}

test('ksef API: runPurchaseSync preferuje async job z pollingiem', () => {
  const source = read('ksef.js');
  assert.match(source, /async function runPurchaseSync\(/);
  assert.match(source, /post\('\/ksef-sessions\/sync-purchase'/);
  assert.match(source, /pollPurchaseSyncJob\(/);
  assert.match(source, /get\(`\/ksef-sessions\/sync-purchase\/jobs\/\$\{jobId\}`\)/);
  assert.match(
    source,
    /try \{[\s\S]*post\('\/ksef-sessions\/sync-purchase'[\s\S]*catch \(err\) \{[\s\S]*404/,
  );
});

test('ksef API: fallback sync ma wydłużony timeout, nie domyślne 30s', () => {
  const source = read('ksef.js');
  assert.match(source, /timeout: 600000/);
});

test('UI Odśwież KSeF: używa runPurchaseSync zamiast syncPurchasesNow', () => {
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
