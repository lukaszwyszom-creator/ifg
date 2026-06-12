import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  evaluateKsefSyncTrigger,
  MISSING_KSEF_SYNC_NIP_MESSAGE,
  resolveKsefSyncNip,
} from './ksefSyncTrigger.js';
import { buildRefreshInvoicePoolTasks } from './invoicePoolRefresh.js';
import { getPurchaseDisplayNumber } from './purchaseInvoiceDisplay.js';

const __dir = dirname(fileURLToPath(import.meta.url));

function read(relativePath) {
  return readFileSync(join(__dir, relativePath), 'utf-8');
}

test('CONNECTED + brak sellerNip: brak cichego return — zwraca komunikat użytkownika', async () => {
  const nip = await resolveKsefSyncNip('', {
    getSettings: async () => ({}),
    getActiveSession: async () => null,
  });
  assert.equal(nip, '');

  const trigger = evaluateKsefSyncTrigger({
    isConnected: true,
    syncBusy: false,
    syncRunning: false,
    nip,
  });

  assert.equal(trigger.action, 'user_error');
  assert.equal(trigger.message, MISSING_KSEF_SYNC_NIP_MESSAGE);
  assert.match(trigger.message, /NIP/);
});

test('KSeFTopbarInfo: handleSyncPurchase nie kończy się cichym return przy pustym sellerNip', () => {
  const source = read('../components/layout/KSeFTopbarInfo.jsx');
  const handleBlock = source.match(/const handleSyncPurchase = async \(\) => \{([\s\S]*?)\n  \};/);
  assert.ok(handleBlock, 'brak handleSyncPurchase');
  const body = handleBlock[1];
  assert.doesNotMatch(body, /if\s*\(\s*!sellerNip\s*\|\|/);
  assert.match(body, /evaluateKsefSyncTrigger/);
  assert.match(body, /trigger\.action === 'user_error'/);
  assert.match(body, /setFlashMsg\(trigger\.message\)/);
});

test('refreshAllInvoicePools: pusty purchase cache planuje pobranie zakupów', () => {
  const filters = { month: '2026-05', status: '', issue_date_from: '', issue_date_to: '', contractor: '' };
  const tasks = buildRefreshInvoicePoolTasks({ sale: {}, purchase: {} }, filters);

  const purchaseBootstrap = tasks.filter(
    (task) => task.direction === 'purchase' && task.source === 'empty_cache',
  );
  assert.equal(purchaseBootstrap.length, 1);
  assert.deepEqual(purchaseBootstrap[0].filters, filters);
  assert.equal(purchaseBootstrap[0].options.defaultToCurrentMonth, false);
});

test('refreshAllInvoicePools: pusty purchase cache wykonuje loadInvoicePool dla purchase', async () => {
  const filters = { month: '2026-05', status: '', issue_date_from: '', issue_date_to: '', contractor: '' };
  const loaded = [];
  const taskSpecs = buildRefreshInvoicePoolTasks({ sale: {}, purchase: {} }, filters, { force: true });

  await Promise.all(taskSpecs.map(async (spec) => {
    loaded.push(spec);
    return [];
  }));

  assert.ok(
    loaded.some((spec) => spec.direction === 'purchase' && spec.source === 'empty_cache'),
    'purchase bootstrap load powinien zostać zaplanowany po syncu',
  );
});

test('refreshAllInvoicePools: useAppStore deleguje do buildRefreshInvoicePoolTasks', () => {
  const source = read('../store/useAppStore.js');
  assert.match(source, /buildRefreshInvoicePoolTasks/);
  assert.match(source, /taskSpecs\.map/);
});

test('getPurchaseDisplayNumber: IFG number_local → fallback do KSeF', () => {
  const result = getPurchaseDisplayNumber({
    number_local: '01/05/2026',
    ksef_reference_number: '20250522-EE-1234567890-ABCD-EF12',
  });

  assert.equal(result.displayNumber, '20250522-EE-1234567890-ABCD-EF12');
  assert.equal(result.numberSource, 'ksef:reference');
});

test('getPurchaseDisplayNumber: P_2 dostawcy pozostaje widoczny', () => {
  const result = getPurchaseDisplayNumber({
    number_local: 'FV/KS/42',
    ksef_reference_number: '20250522-EE-1234567890-ABCD-EF12',
  });

  assert.equal(result.displayNumber, 'FV/KS/42');
  assert.equal(result.numberSource, 'ksef:P_2');
});

test('getPurchaseDisplayNumber: format FV/n/mm/yyyy traktowany jako IFG', () => {
  const result = getPurchaseDisplayNumber({
    number_local: 'FV/12/05/2026',
    ksef_reference_number: 'KSEF-REF-99',
  });

  assert.equal(result.displayNumber, 'KSEF-REF-99');
  assert.equal(result.numberSource, 'ksef:reference');
});
