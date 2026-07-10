import test from 'node:test';
import assert from 'node:assert/strict';
import {
  aggregateGroupStatus,
  buildInvoiceSnapshot,
  buildProcessSummaryMeta,
  buildSummaryLines,
  deriveProcessProgress,
  deriveProcessIcon,
  deriveProcessKey,
  deriveProcessTitle,
  deriveRowStatusTone,
  filterAndSearchGroups,
  groupMatchesFilter,
  groupMatchesSearch,
  formatDateTimeWithWeekday,
  formatGroupStatusDisplay,
  mapStatusKeyToTone,
  MONITOR_FILTERS,
  formatOperatorDateTime,
  formatTransmissionMarker,
  groupTransmissions,
  extractInvoicesFromRows,
  invoiceHasTooltipDetails,
  invoicesSummaryLabel,
  summarizeGroup,
} from './transmissionUtils.js';

const baseRow = (overrides = {}) => ({
  id: '1',
  invoice_id: null,
  channel: 'ksef',
  operation_type: 'SESSION_REFRESH',
  severity: 'SUCCESS',
  correlation_id: 'corr-1',
  job_id: null,
  status: 'success',
  attempt_no: 1,
  ksef_reference_number: null,
  upo_status: null,
  error_message: null,
  metadata_json: { description: 'ok' },
  created_at: '2026-07-08T08:00:06.000Z',
  finished_at: '2026-07-08T08:00:11.000Z',
  invoice_number_local: null,
  ...overrides,
});

test('formatTransmissionMarker zwraca ddmmyyyyggmmss (14 cyfr)', () => {
  const marker = formatTransmissionMarker('2026-07-08T08:00:06.000Z');
  assert.match(marker, /^\d{14}$/);
});

test('formatDateTimeWithWeekday zwraca datę i dzień tygodnia po polsku', () => {
  const { dateLine, timeLine } = formatDateTimeWithWeekday('2026-07-08T12:00:00.000Z');
  assert.match(dateLine, /^08\.07\.2026 \(środa\)$/);
  assert.match(timeLine, /^\d{2}:\d{2}$/);
});

test('deriveProcessKey preferuje job_id nad correlation_id', () => {
  assert.equal(
    deriveProcessKey(baseRow({ job_id: 'job-9', correlation_id: 'corr-1' })),
    'job:job-9',
  );
});

test('groupTransmissions grupuje po correlation_id gdy brak job_id', () => {
  const rows = [
    baseRow({ id: 'a', job_id: null, correlation_id: 'corr-1' }),
    baseRow({ id: 'b', job_id: null, correlation_id: 'corr-1' }),
  ];
  const groups = groupTransmissions(rows);
  assert.equal(groups.length, 1);
  assert.ok(groups[0].dateTimeParts?.dateLine?.includes('(') || groups[0].datetime.includes('('));
});

test('aggregateGroupStatus: zakończona synchronizacja zakupów mimo wpisu started RUNNING', () => {
  const rows = [
    baseRow({
      id: '1',
      operation_type: 'PURCHASE_SYNC_AUTO',
      status: 'started',
      severity: 'RUNNING',
      created_at: '2026-07-08T12:00:01.000Z',
    }),
    baseRow({
      id: '2',
      operation_type: 'PURCHASE_METADATA_FETCH',
      status: 'success',
      severity: 'INFO',
      created_at: '2026-07-08T12:00:06.000Z',
    }),
    baseRow({
      id: '3',
      operation_type: 'PURCHASE_IMPORT_SUMMARY',
      status: 'summary',
      severity: 'INFO',
      metadata_json: { saved: 12 },
      created_at: '2026-07-08T12:00:06.500Z',
    }),
    baseRow({
      id: '4',
      operation_type: 'PURCHASE_SYNC_AUTO',
      status: 'ok',
      severity: 'SUCCESS',
      created_at: '2026-07-08T12:00:07.000Z',
    }),
  ];
  assert.equal(aggregateGroupStatus(rows).key, 'success');
  assert.equal(formatGroupStatusDisplay(aggregateGroupStatus(rows)), '✔ Sukces');
});

test('aggregateGroupStatus: sesja KSeF z refreshed nie jest W TOKU', () => {
  const rows = [
    baseRow({
      id: '1',
      operation_type: 'SESSION_RENEWED',
      status: 'authenticated',
      severity: 'SUCCESS',
      created_at: '2026-07-08T10:00:00.000Z',
    }),
    baseRow({
      id: '2',
      operation_type: 'SESSION_REFRESH',
      status: 'refreshed',
      severity: 'SUCCESS',
      created_at: '2026-07-08T10:00:05.000Z',
    }),
  ];
  assert.equal(aggregateGroupStatus(rows).key, 'success');
});

test('aggregateGroupStatus: scheduler skip nie jest W TOKU', () => {
  const rows = [
    baseRow({
      id: '1',
      operation_type: 'SCHEDULER_ENQUEUE',
      status: 'enqueued',
      severity: 'SUCCESS',
      created_at: '2026-07-08T14:00:00.000Z',
    }),
    baseRow({
      id: '2',
      operation_type: 'SCHEDULER_SKIP_ALREADY_EXECUTED',
      status: 'skipped',
      severity: 'INFO',
      created_at: '2026-07-08T14:00:01.000Z',
    }),
    baseRow({
      id: '3',
      operation_type: 'SCHEDULER_SLOT',
      status: 'slot_due',
      severity: 'RUNNING',
      created_at: '2026-07-08T14:00:00.500Z',
    }),
  ];
  assert.notEqual(aggregateGroupStatus(rows).key, 'running');
});

test('aggregateGroupStatus: aktywny worker pipeline jest W TOKU', () => {
  const rows = [
    baseRow({
      operation_type: 'SALE_SEND',
      status: 'waiting_status',
      severity: 'RUNNING',
      created_at: '2026-07-08T15:00:00.000Z',
    }),
  ];
  assert.equal(aggregateGroupStatus(rows).key, 'running');
});

test('aggregateGroupStatus zwraca BŁĄD i OSTRZEŻENIE', () => {
  assert.equal(aggregateGroupStatus([baseRow()]).key, 'success');
  assert.equal(
    aggregateGroupStatus([baseRow({ severity: 'ERROR', status: 'failed_permanent' })]).key,
    'error',
  );
  assert.equal(
    aggregateGroupStatus([baseRow({ severity: 'WARNING', status: 'failed_retryable' })]).key,
    'warning',
  );
});

test('buildInvoiceSnapshot używa invoice_snapshot z API', () => {
  const snap = buildInvoiceSnapshot(baseRow({
    invoice_id: 'inv-1',
    invoice_number_local: 'FV/1/2026',
    operation_type: 'SALE_SEND',
    invoice_snapshot: {
      number: 'FV/1/2026',
      counterparty_name: 'Nabywca Sp. z o.o.',
      counterparty_nip: '1234567890',
      gross_total: '1230.00',
      currency: 'PLN',
      issue_date: '2026-07-01',
      ksef_reference_number: 'KSeF-001',
      status: 'accepted',
      direction: 'sale',
    },
  }));
  assert.equal(snap.counterparty, 'Nabywca Sp. z o.o.');
  assert.equal(snap.nip, '1234567890');
  assert.equal(snap.amount, '1230,00 PLN');
  assert.equal(snap.ksefRef, 'KSeF-001');
  assert.equal(snap.direction, 'sale');
});

test('formatOperatorDateTime używa Dzisiaj i Wczoraj', () => {
  const now = new Date(2026, 6, 9, 15, 0, 0);
  const today = formatOperatorDateTime(new Date(2026, 6, 9, 14, 0, 0), now);
  assert.match(today.dateLine, /^Dzisiaj \(czwartek\)$/);
  assert.equal(today.timeLine, '14:00');

  const yesterday = formatOperatorDateTime(new Date(2026, 6, 8, 9, 12, 0), now);
  assert.match(yesterday.dateLine, /^Wczoraj \(środa\)$/);
  assert.equal(yesterday.timeLine, '09:12');

  const older = formatOperatorDateTime(new Date(2026, 6, 7, 18, 44, 0), now);
  assert.match(older.dateLine, /^07\.07\.2026 \(wtorek\)$/);
  assert.equal(older.timeLine, '18:44');
});

test('deriveProcessIcon rozpoznaje typ procesu', () => {
  assert.equal(deriveProcessIcon('Synchronizacja zakupów', { key: 'success' }), '📥');
  assert.equal(deriveProcessIcon('Wysyłka sprzedaży', { key: 'success' }), '📤');
  assert.equal(deriveProcessIcon('Sesja KSeF', { key: 'success' }), '🔐');
  assert.equal(deriveProcessIcon('Harmonogram KSeF', { key: 'success' }), '⏰');
});

test('mapStatusKeyToTone mapuje klucz statusu do tonu UX', () => {
  assert.equal(mapStatusKeyToTone('success'), 'success');
  assert.equal(mapStatusKeyToTone('info'), 'info');
  assert.equal(mapStatusKeyToTone('waiting_status'), 'warning');
  assert.equal(mapStatusKeyToTone('failed_retryable'), 'warning');
  assert.equal(mapStatusKeyToTone('failed_permanent'), 'error');
  assert.equal(mapStatusKeyToTone('neutral'), 'neutral');
});

test('deriveRowStatusTone preferuje błąd/ostrzeżenie nad info', () => {
  assert.equal(deriveRowStatusTone(baseRow({ severity: 'SUCCESS', status: 'success' })), 'success');
  assert.equal(deriveRowStatusTone(baseRow({ severity: 'INFO', status: 'submitted' })), 'info');
  assert.equal(deriveRowStatusTone(baseRow({ severity: 'RUNNING', status: 'waiting_status' })), 'warning');
  assert.equal(deriveRowStatusTone(baseRow({ severity: 'WARNING', status: 'ok' })), 'warning');
  assert.equal(deriveRowStatusTone(baseRow({ severity: 'ERROR', status: 'failed_permanent' })), 'error');
});

test('invoiceHasTooltipDetails wykrywa brak danych', () => {
  assert.equal(invoiceHasTooltipDetails(buildInvoiceSnapshot(baseRow({
    invoice_id: 'inv-1',
    invoice_number_local: 'FV/1',
    invoice_snapshot: {
      number: 'FV/1',
      counterparty_name: 'Firma',
      counterparty_nip: '123',
      gross_total: '100',
      currency: 'PLN',
      direction: 'sale',
    },
  }))), true);

  assert.equal(invoiceHasTooltipDetails(buildInvoiceSnapshot(baseRow({
    invoice_id: 'inv-2',
    invoice_number_local: 'FV/2',
    metadata_json: { description: 'journal only' },
  }))), false);
});

test('buildProcessSummaryMeta kończy się etapami', () => {
  const summary = summarizeGroup([
    baseRow({
      operation_type: 'PURCHASE_IMPORT_SUMMARY',
      metadata_json: { saved: 12 },
      started_at: null,
      finished_at: null,
    }),
  ]);
  assert.equal(summary.purchaseSaved, 12);
  const meta = buildProcessSummaryMeta(summary, 'Synchronizacja zakupów');
  assert.ok(meta.startsWith('12 nowych faktur'));
  assert.ok(meta.includes('etap'));
});

test('summarizeGroup pokazuje liczbę nowych faktur zakupu', () => {
  const summary = summarizeGroup([
    baseRow({
      operation_type: 'PURCHASE_IMPORT_SUMMARY',
      metadata_json: { saved: 12 },
      started_at: null,
      finished_at: null,
    }),
  ]);
  assert.equal(summary.purchaseSaved, 12);
});

test('buildSummaryLines pokazuje efekt procesu sprzedaży', () => {
  const rows = [
    baseRow({
      invoice_id: 'inv-1',
      invoice_number_local: 'FV/123/2026',
      operation_type: 'SALE_SEND',
      upo_status: 'fetched',
      ksef_reference_number: 'KSeF-XYZ',
    }),
  ];
  const summary = summarizeGroup(rows);
  const lines = buildSummaryLines(summary, aggregateGroupStatus(rows), 'Wysyłka sprzedaży');
  assert.ok(lines.effects.some((l) => l.includes('FV/123/2026')));
  assert.ok(lines.effects.some((l) => l.includes('UPO')));
  assert.ok(lines.meta.some((l) => l.includes('etap')));
});

test('extractInvoicesFromRows deduplikuje faktury w grupie', () => {
  const rows = [
    baseRow({
      invoice_id: 'inv-1',
      invoice_number_local: 'FV/1/2026',
      operation_type: 'SALE_SEND',
    }),
    baseRow({
      id: '2',
      invoice_id: 'inv-1',
      invoice_number_local: 'FV/1/2026',
      operation_type: 'SALE_STATUS',
    }),
  ];
  assert.equal(extractInvoicesFromRows(rows).length, 1);
});

test('invoicesSummaryLabel pokazuje liczbę faktur', () => {
  const summary = summarizeGroup([
    baseRow({ invoice_id: '1', invoice_number_local: 'FV/1' }),
    baseRow({ id: '2', invoice_id: '2', invoice_number_local: 'FV/2' }),
  ]);
  assert.equal(invoicesSummaryLabel(summary), '2 faktur');
});

test('invoicesSummaryLabel pokazuje numer i kontrahenta dla jednej faktury z invoice_snapshot', () => {
  const summary = summarizeGroup([
    baseRow({
      invoice_id: '1',
      invoice_number_local: 'FV/123/2026',
      invoice_snapshot: {
        number: 'FV/123/2026',
        counterparty_name: 'ACME Sp. z o.o.',
        counterparty_nip: '1234567890',
        gross_total: '1230.00',
        currency: 'PLN',
        direction: 'sale',
      },
    }),
  ]);
  assert.equal(invoicesSummaryLabel(summary), 'FV/123/2026 · ACME Sp. z o.o.');
});

test('invoicesSummaryLabel dla jednej faktury bez invoice_snapshot pokazuje sam numer', () => {
  const summary = summarizeGroup([
    baseRow({
      invoice_id: '1',
      invoice_number_local: 'FV/123/2026',
      metadata_json: { description: 'journal only' },
    }),
  ]);
  assert.equal(invoicesSummaryLabel(summary), 'FV/123/2026');
});

test('groupTransmissions wydajnie obsługuje dużą liczbę wierszy', () => {
  const rows = Array.from({ length: 500 }, (_, i) => baseRow({
    id: String(i),
    job_id: `job-${i % 25}`,
    correlation_id: `corr-${i}`,
  }));
  const start = Date.now();
  const groups = groupTransmissions(rows);
  const elapsed = Date.now() - start;
  assert.equal(groups.length, 25);
  assert.ok(elapsed < 100, `grouping too slow: ${elapsed}ms`);
});

test('MONITOR_FILTERS zawiera wszystkie filtry UX', () => {
  const keys = MONITOR_FILTERS.map((f) => f.key);
  assert.deepEqual(keys, ['all', 'sale', 'purchase', 'active', 'errors', 'finished']);
});

test('groupMatchesFilter: filtr Wszystkie przepuszcza grupę', () => {
  const group = groupTransmissions([baseRow({ operation_type: 'SALE_SEND' })])[0];
  assert.equal(groupMatchesFilter(group, 'all'), true);
});

test('groupMatchesFilter: filtr Sprzedaż i Zakupy', () => {
  const saleGroup = groupTransmissions([baseRow({ operation_type: 'SALE_SEND' })])[0];
  const purchaseGroup = groupTransmissions([baseRow({ operation_type: 'PURCHASE_SYNC_AUTO' })])[0];
  assert.equal(groupMatchesFilter(saleGroup, 'sale'), true);
  assert.equal(groupMatchesFilter(saleGroup, 'purchase'), false);
  assert.equal(groupMatchesFilter(purchaseGroup, 'purchase'), true);
  assert.equal(groupMatchesFilter(purchaseGroup, 'sale'), false);
});

test('groupMatchesFilter: filtr Aktywne', () => {
  const active = groupTransmissions([baseRow({ operation_type: 'SALE_SEND', status: 'waiting_status', severity: 'RUNNING' })])[0];
  const finished = groupTransmissions([baseRow({ operation_type: 'SALE_SEND', status: 'success', severity: 'SUCCESS' })])[0];
  assert.equal(groupMatchesFilter(active, 'active'), true);
  assert.equal(groupMatchesFilter(finished, 'active'), false);
});

test('groupMatchesFilter: filtr Błędy', () => {
  const errorGroup = groupTransmissions([baseRow({ operation_type: 'SALE_SEND', status: 'failed_permanent', severity: 'ERROR' })])[0];
  const warningGroup = groupTransmissions([baseRow({ operation_type: 'SALE_SEND', status: 'failed_retryable', severity: 'WARNING' })])[0];
  const successGroup = groupTransmissions([baseRow({ operation_type: 'SALE_SEND', status: 'success', severity: 'SUCCESS' })])[0];
  assert.equal(groupMatchesFilter(errorGroup, 'errors'), true);
  assert.equal(groupMatchesFilter(warningGroup, 'errors'), true);
  assert.equal(groupMatchesFilter(successGroup, 'errors'), false);
});

test('groupMatchesFilter: filtr Zakończone oraz brak wyników', () => {
  const runningGroup = groupTransmissions([baseRow({ operation_type: 'SALE_SEND', status: 'processing', severity: 'RUNNING' })])[0];
  const successGroup = groupTransmissions([baseRow({ operation_type: 'SALE_SEND', status: 'success', severity: 'SUCCESS' })])[0];
  const filtered = [runningGroup].filter((g) => groupMatchesFilter(g, 'finished'));
  assert.equal(groupMatchesFilter(successGroup, 'finished'), true);
  assert.equal(groupMatchesFilter(runningGroup, 'finished'), false);
  assert.equal(filtered.length, 0);
});

test('groupMatchesSearch: numer FV i częściowe dopasowanie', () => {
  const group = groupTransmissions([baseRow({
    operation_type: 'SALE_SEND',
    invoice_id: 'inv-1',
    invoice_number_local: 'FV/123/2026',
  })])[0];
  assert.equal(groupMatchesSearch(group, 'fv/123'), true);
  assert.equal(groupMatchesSearch(group, 'FV/123'), true);
  assert.equal(groupMatchesSearch(group, 'fv/999'), false);
});

test('groupMatchesSearch: kontrahent i case insensitive', () => {
  const group = groupTransmissions([baseRow({
    operation_type: 'SALE_SEND',
    invoice_id: 'inv-1',
    invoice_number_local: 'FV/123/2026',
    invoice_snapshot: {
      number: 'FV/123/2026',
      counterparty_name: 'ACME Sp. z o.o.',
      direction: 'sale',
    },
  })])[0];
  assert.equal(groupMatchesSearch(group, 'acme'), true);
  assert.equal(groupMatchesSearch(group, 'AcMe'), true);
});

test('groupMatchesSearch: numer KSeF, transmission id, correlation id, job id', () => {
  const group = groupTransmissions([baseRow({
    id: 'tx-001',
    transmission_id: 'tx-001',
    correlation_id: 'corr-xyz',
    job_id: 'job-777',
    operation_type: 'SALE_SEND',
    ksef_reference_number: 'KSEF-ABC-123',
  })])[0];
  assert.equal(groupMatchesSearch(group, 'ksef-abc'), true);
  assert.equal(groupMatchesSearch(group, 'tx-001'), true);
  assert.equal(groupMatchesSearch(group, 'corr-xyz'), true);
  assert.equal(groupMatchesSearch(group, 'job-777'), true);
});

test('groupMatchesSearch: tytuł procesu', () => {
  const purchase = groupTransmissions([baseRow({ operation_type: 'PURCHASE_SYNC_AUTO' })])[0];
  assert.equal(groupMatchesSearch(purchase, 'synchronizacja zakupów'), true);
});

test('filterAndSearchGroups: współpraca filtrów i wyszukiwania', () => {
  const groups = groupTransmissions([
    baseRow({
      id: '1',
      correlation_id: 'corr-sale',
      operation_type: 'SALE_SEND',
      severity: 'ERROR',
      status: 'failed_permanent',
      invoice_id: 'inv-a',
      invoice_number_local: 'FV/A/2026',
      invoice_snapshot: { number: 'FV/A/2026', counterparty_name: 'ALFA', direction: 'sale' },
    }),
    baseRow({
      id: '2',
      correlation_id: 'corr-purchase',
      operation_type: 'PURCHASE_SYNC_AUTO',
      severity: 'SUCCESS',
      status: 'success',
      invoice_id: 'inv-b',
      invoice_number_local: 'FV/B/2026',
      invoice_snapshot: { number: 'FV/B/2026', counterparty_name: 'BETA', direction: 'purchase' },
    }),
  ]);
  const result = filterAndSearchGroups(groups, 'errors', 'alfa');
  assert.equal(result.length, 1);
  assert.equal(result[0].title, 'Wysyłka sprzedaży');
});

test('filterAndSearchGroups: brak wyników wyszukiwania', () => {
  const groups = groupTransmissions([baseRow({ operation_type: 'SALE_SEND', invoice_number_local: 'FV/1/2026' })]);
  const result = filterAndSearchGroups(groups, 'all', 'nie-ma');
  assert.equal(result.length, 0);
});

test('deriveProcessProgress: proces zakończony sukcesem ma 100%', () => {
  const group = groupTransmissions([
    baseRow({ correlation_id: 'sale-1', operation_type: 'SALE_SEND', status: 'success', severity: 'SUCCESS' }),
    baseRow({ id: '2', correlation_id: 'sale-1', operation_type: 'SALE_STATUS', status: 'ok', severity: 'SUCCESS' }),
    baseRow({ id: '3', correlation_id: 'sale-1', operation_type: 'UPO_DOWNLOAD', status: 'downloaded', severity: 'SUCCESS', upo_status: 'fetched' }),
  ])[0];
  const progress = deriveProcessProgress(group);
  assert.equal(progress.percent, 100);
  assert.equal(progress.tone, 'success');
});

test('deriveProcessProgress: proces w toku pokazuje active i ton info', () => {
  const group = groupTransmissions([
    baseRow({ correlation_id: 'sale-2', operation_type: 'SALE_SEND', status: 'processing', severity: 'RUNNING' }),
  ])[0];
  const progress = deriveProcessProgress(group);
  assert.equal(progress.tone, 'info');
  assert.ok(progress.steps.some((step) => step.status === 'active'));
});

test('deriveProcessProgress: proces z błędem ma ton danger', () => {
  const group = groupTransmissions([
    baseRow({ correlation_id: 'sale-3', operation_type: 'SALE_SEND', status: 'failed_permanent', severity: 'ERROR' }),
  ])[0];
  const progress = deriveProcessProgress(group);
  assert.equal(progress.tone, 'danger');
});

test('deriveProcessProgress: proces z ostrzeżeniem/retry ma ton warning', () => {
  const group = groupTransmissions([
    baseRow({ correlation_id: 'sale-4', operation_type: 'SALE_SEND', status: 'failed_retryable', severity: 'WARNING' }),
  ])[0];
  const progress = deriveProcessProgress(group);
  assert.equal(progress.tone, 'warning');
});

test('deriveProcessProgress: rozpoznaje etapy synchronizacji zakupów', () => {
  const group = groupTransmissions([
    baseRow({ correlation_id: 'purchase-1', operation_type: 'SESSION_REFRESH', status: 'success', severity: 'SUCCESS' }),
    baseRow({ id: '2', correlation_id: 'purchase-1', operation_type: 'PURCHASE_METADATA_FETCH', status: 'ok', severity: 'SUCCESS' }),
    baseRow({ id: '3', correlation_id: 'purchase-1', operation_type: 'PURCHASE_INVOICE_FETCH', status: 'ok', severity: 'SUCCESS' }),
    baseRow({ id: '4', correlation_id: 'purchase-1', operation_type: 'PURCHASE_IMPORT_SUMMARY', status: 'summary', severity: 'SUCCESS' }),
  ])[0];
  const progress = deriveProcessProgress(group);
  const stepKeys = progress.steps.map((s) => s.key);
  assert.ok(stepKeys.includes('metadata'));
  assert.ok(stepKeys.includes('xml'));
  assert.ok(stepKeys.includes('import'));
});

test('deriveProcessProgress: rozpoznaje etapy wysyłki sprzedaży', () => {
  const group = groupTransmissions([
    baseRow({ correlation_id: 'sale-5', operation_type: 'SALE_SEND', status: 'success', severity: 'SUCCESS' }),
    baseRow({ id: '2', correlation_id: 'sale-5', operation_type: 'SALE_STATUS', status: 'ok', severity: 'SUCCESS' }),
    baseRow({ id: '3', correlation_id: 'sale-5', operation_type: 'UPO_DOWNLOAD', status: 'downloaded', severity: 'SUCCESS', upo_status: 'fetched' }),
  ])[0];
  const progress = deriveProcessProgress(group);
  const stepKeys = progress.steps.map((s) => s.key);
  assert.ok(stepKeys.includes('send'));
  assert.ok(stepKeys.includes('status'));
  assert.ok(stepKeys.includes('upo'));
});

test('deriveProcessProgress: fallback dla nierozpoznanego procesu', () => {
  const group = groupTransmissions([
    baseRow({ correlation_id: 'custom-1', operation_type: 'CUSTOM_STAGE', status: 'processing', severity: 'RUNNING' }),
  ])[0];
  group.title = 'Nietypowy proces';
  const progress = deriveProcessProgress(group);
  assert.equal(progress.fallback, false);
  assert.equal(progress.steps.length, 3);
});
