/**
 * Testy jednostkowe dla logiki agregacji Zestawień.
 * Uruchamianie: node --test src/components/dashboard/dashboardAggregation.test.js
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { buildPlnSummary } from './dashboardAggregation.js';

const __dir = dirname(fileURLToPath(import.meta.url));

// ── Aggregation logic ─────────────────────────────────────────────────────────

test('buildPlnSummary: puste zwraca zera', () => {
  const r = buildPlnSummary([]);
  assert.equal(r.netto,  0);
  assert.equal(r.vat,    0);
  assert.equal(r.brutto, 0);
});

test('buildPlnSummary: sumuje accepted PLN', () => {
  const invoices = [
    { status: 'accepted', currency: 'PLN', total_net: '100.00', total_vat: '23.00', total_gross: '123.00' },
    { status: 'accepted', currency: 'PLN', total_net: '200.00', total_vat: '46.00', total_gross: '246.00' },
  ];
  const r = buildPlnSummary(invoices);
  assert.equal(r.netto,  300);
  assert.equal(r.vat,    69);
  assert.equal(r.brutto, 369);
});

test('buildPlnSummary: sumuje ready_for_submission i sending', () => {
  const invoices = [
    { status: 'ready_for_submission', currency: 'PLN', total_net: '50.00', total_vat: '11.50', total_gross: '61.50' },
    { status: 'sending',              currency: 'PLN', total_net: '50.00', total_vat: '11.50', total_gross: '61.50' },
  ];
  const r = buildPlnSummary(invoices);
  assert.equal(r.netto,  100);
  assert.equal(r.vat,    23);
  assert.equal(r.brutto, 123);
});

test('buildPlnSummary: wyklucza rejected', () => {
  const invoices = [
    { status: 'accepted', currency: 'PLN', total_net: '100.00', total_vat: '23.00', total_gross: '123.00' },
    { status: 'rejected', currency: 'PLN', total_net: '999.00', total_vat: '999.00', total_gross: '999.00' },
  ];
  const r = buildPlnSummary(invoices);
  assert.equal(r.netto,  100);
  assert.equal(r.vat,    23);
  assert.equal(r.brutto, 123);
});

test('buildPlnSummary: wyklucza faktury walutowe (EUR)', () => {
  const invoices = [
    { status: 'accepted', currency: 'PLN', total_net: '100.00', total_vat: '23.00', total_gross: '123.00' },
    { status: 'accepted', currency: 'EUR', total_net: '500.00', total_vat: '115.00', total_gross: '615.00' },
  ];
  const r = buildPlnSummary(invoices);
  assert.equal(r.netto,  100);
  assert.equal(r.vat,    23);
  assert.equal(r.brutto, 123);
});

test('buildPlnSummary: waluta domyślna PLN gdy brak pola currency', () => {
  const invoices = [
    { status: 'accepted', total_net: '80.00', total_vat: '18.40', total_gross: '98.40' },
  ];
  const r = buildPlnSummary(invoices);
  assert.equal(r.netto,  80);
  assert.equal(r.brutto, 98.40);
});

test('buildPlnSummary: brutto = netto + vat (zaokrąglenie do 2 miejsc)', () => {
  const invoices = [
    { status: 'accepted', currency: 'PLN', total_net: '33.33', total_vat: '7.67', total_gross: '41.00' },
    { status: 'accepted', currency: 'PLN', total_net: '33.33', total_vat: '7.67', total_gross: '41.00' },
    { status: 'accepted', currency: 'PLN', total_net: '33.34', total_vat: '7.66', total_gross: '41.00' },
  ];
  const r = buildPlnSummary(invoices);
  assert.equal(r.netto,  100);
  assert.equal(r.vat,    23);
  assert.equal(r.brutto, 123);
});

// ── Navigation labels ─────────────────────────────────────────────────────────

test('Sidebar: nie zawiera etykiety "Dashboard"', () => {
  const src = readFileSync(
    join(__dir, '../layout/Sidebar.jsx'),
    'utf-8',
  );
  // Upewnij się że stara etykieta nawigacyjna zniknęła
  assert.ok(
    !src.includes("label: 'Dashboard'"),
    'Sidebar nie powinien mieć etykiety "Dashboard"',
  );
});

test('Sidebar: zawiera etykietę "Sprzedaż / Zakup"', () => {
  const src = readFileSync(
    join(__dir, '../layout/Sidebar.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes('Sprzeda\u017c / Zakup'),
    'Sidebar powinien mieć etykietę "Sprzedaż / Zakup"',
  );
});

test('Sidebar: etykieta faktur sprzedaży jest stała (bez miesiąca)', () => {
  const src = readFileSync(
    join(__dir, '../layout/Sidebar.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes("label: 'Faktury sprzedaży'"),
    'Sidebar powinien mieć stałą etykietę "Faktury sprzedaży"',
  );
  assert.ok(
    !src.includes('Faktury -'),
    'Sidebar nie powinien dynamicznie doklejać miesiąca do etykiety faktur',
  );
});

test('Sidebar: nav item i label mają white-space nowrap (jedna linia)', () => {
  const src = readFileSync(
    join(__dir, '../layout/Sidebar.module.css'),
    'utf-8',
  );
  assert.ok(src.includes('.navItem') && src.includes('white-space: nowrap;'), 'brak nowrap w .navItem');
  assert.ok(src.includes('.navLabel') && src.includes('white-space: nowrap;'), 'brak nowrap w .navLabel');
});

test('Topbar: nie zawiera stringa "Dashboard" jako stringa tytułu', () => {
  const src = readFileSync(
    join(__dir, '../layout/Topbar.jsx'),
    'utf-8',
  );
  assert.ok(
    !src.includes("'Dashboard'"),
    'Topbar nie powinien zawierać "\'Dashboard\'" jako tytułu',
  );
});

test('Topbar: zawiera tytuł "Zestawienia: sprzedaż / zakup"', () => {
  const src = readFileSync(
    join(__dir, '../layout/Topbar.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes('Zestawienia: sprzeda\u017c / zakup'),
    'Topbar powinien zawierać "Zestawienia: sprzedaż / zakup"',
  );
});

// ── DashboardSummary source: brak EUR i Różnicy kursowej ─────────────────────

test('DashboardSummary: nie renderuje EUR w legendzie', () => {
  const src = readFileSync(
    join(__dir, './DashboardSummary.jsx'),
    'utf-8',
  );
  // Nie powinno być żadnego wzorca wyświetlającego obcą walutę w legendzie/podsumowaniu
  assert.ok(
    !src.includes('legendForeign'),
    'DashboardSummary nie powinien używać klasy legendForeign',
  );
});

test('DashboardSummary: nie renderuje "Różnica kursowa"', () => {
  const src = readFileSync(
    join(__dir, './DashboardSummary.jsx'),
    'utf-8',
  );
  assert.ok(
    !src.includes('R\u00f3\u017cnica kursowa'),
    'DashboardSummary nie powinien renderować "Różnica kursowa"',
  );
});

test('DashboardSummary: summaryBar pokazuje SPRZEDAŻ Netto/VAT/Brutto i ZAKUP Netto/VAT/Brutto', () => {
  const src = readFileSync(
    join(__dir, './DashboardSummary.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('SPRZEDA\u017b'),   'brak etykiety SPRZEDAŻ');
  assert.ok(src.includes('ZAKUP'),            'brak etykiety ZAKUP');
  assert.ok(src.includes('saleSummary.netto'),    'brak saleSummary.netto');
  assert.ok(src.includes('saleSummary.vat'),      'brak saleSummary.vat');
  assert.ok(src.includes('saleSummary.brutto'),   'brak saleSummary.brutto');
  assert.ok(src.includes('purchaseSummary.netto'),  'brak purchaseSummary.netto');
  assert.ok(src.includes('purchaseSummary.vat'),    'brak purchaseSummary.vat');
  assert.ok(src.includes('purchaseSummary.brutto'), 'brak purchaseSummary.brutto');
});

test('DashboardSummary: używa klas CSS periodPrefix i periodAccent', () => {
  const src = readFileSync(
    join(__dir, './DashboardSummary.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('periodPrefix'), 'brak klasy periodPrefix');
  assert.ok(src.includes('periodAccent'), 'brak klasy periodAccent');
});

test('DashboardSummary: używa klasy summaryBar', () => {
  const src = readFileSync(
    join(__dir, './DashboardSummary.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('summaryBar'), 'brak klasy summaryBar');
});

test('InvoiceCardList: obsługuje warunkowe ukrycie kolumny Status KSeF', () => {
  const src = readFileSync(
    join(__dir, '../invoice/InvoiceCardList.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('showKsefStatus'), 'brak flagi showKsefStatus');
  assert.ok(src.includes('Status KSeF'), 'brak kolumny Status KSeF w komponencie');
});

test('InvoiceCardList: dla zakupów używa nagłówka Sprzedawca', () => {
  const src = readFileSync(
    join(__dir, '../invoice/InvoiceCardList.jsx'),
    'utf-8',
  );
  assert.ok(src.includes("direction === 'purchase' ? 'Sprzedawca' : 'Nabywca'"), 'brak logiki Sprzedawca/Nabywca');
});

test('AdvancedDashboard: ukrywa kolumnę Status KSeF w zestawieniach sprzedaży i zakupu', () => {
  const src = readFileSync(
    join(__dir, '../../pages/advanced/AdvancedDashboard.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('showKsefStatus={false}'), 'brak wyłączenia showKsefStatus w dashboardzie');
});

test('SimpleView: selectedMonth steruje filtrem month i nagłówkiem sprzedaży', () => {
  const src = readFileSync(
    join(__dir, '../../pages/simple/SimpleView.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('selectedMonth'), 'brak stanu selectedMonth');
  assert.ok(src.includes('filters={saleMonthFilters}'), 'InvoiceList powinien używać selectedMonth przez saleMonthFilters');
  assert.ok(src.includes('Suma sprzedaży wybranego miesiąca:'), 'brak nagłówka podsumowania miesiąca');
  assert.ok(src.includes('Brak faktur sprzedaży w ${selectedMonthLocative}'), 'brak pustego stanu zależnego od selectedMonth');
});

test('InvoiceList: ignoruje stare odpowiedzi requestów (race condition miesiąca)', () => {
  const src = readFileSync(
    join(__dir, '../invoice/InvoiceList.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('requestSeqRef'), 'brak sekwencji requestów chroniącej przed stale response');
  assert.ok(src.includes('const requestSeq = ++requestSeqRef.current;'), 'brak inkrementacji sekwencji per request');
  assert.ok(src.includes('if (requestSeq !== requestSeqRef.current) return;'), 'brak guardu ignorującego stary response');
  assert.ok(src.includes('requestSeqRef.current += 1;'), 'brak unieważniania requestów przy unmount');
});

test('InvoiceList: przy filters.month odfiltrowuje odpowiedź po issue_date na ten miesiąc', () => {
  const src = readFileSync(
    join(__dir, '../invoice/InvoiceList.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('const rawItems = Array.isArray(res?.items) ? res.items : [];'), 'brak normalizacji listy odpowiedzi');
  assert.ok(src.includes("rawItems.filter((inv) => String(inv?.issue_date || '').slice(0, 7) === monthFilter)"), 'brak guardu filtrującego po issue_date i monthFilter');
  assert.ok(src.includes('onItemsChange(items);'), 'onItemsChange powinno dostawać już odfiltrowane elementy');
});

test('VATSummary: nie mapuje nieparsowalnej stawki VAT do 0%', () => {
  const src = readFileSync(
    join(__dir, './VATSummary.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes("if (rate === null) return 'inne';"),
    'nieparsowalna stawka VAT powinna trafiać do bucketu "inne"',
  );
  assert.ok(
    !src.includes('const rate = toNum(item?.vat_rate);'),
    'resolveRate nie powinien już używać toNum dla vat_rate',
  );
});

test('VATSummary: parsuje stawki z przecinkiem i symbolem %', () => {
  const src = readFileSync(
    join(__dir, './VATSummary.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes("replace('%', '')") && src.includes("replace(',', '.')"),
    'normalizacja vat_rate powinna obsługiwać zapis "23%" i "23,0"',
  );
});

test('VATSummary: bucket 0% zawsze wymusza VAT = 0', () => {
  const src = readFileSync(
    join(__dir, './VATSummary.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes("const vat = rate === '0' ? 0 : toNum(item.vat_total);"),
    'dla stawki 0% VAT musi być wymuszony na 0 niezależnie od wartości z item.vat_total',
  );
});

test('VATSummary: parsuje wariant stawki VAT_0', () => {
  const src = readFileSync(
    join(__dir, './VATSummary.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes('normalized.match(/-?\\d+(?:\\.\\d+)?/)'),
    'toNumericRate powinno wyciągać token liczbowy także z formatu VAT_0',
  );
});
