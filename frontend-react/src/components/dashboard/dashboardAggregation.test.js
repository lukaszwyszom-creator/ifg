/**
 * Testy jednostkowe dla logiki agregacji Zestawień.
 * Uruchamianie: node --test src/components/dashboard/dashboardAggregation.test.js
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { buildPlnSummary, buildYtdBarHeights } from './dashboardAggregation.js';
import { currentYearToDateRange } from './dashboardQuery.js';
import { extractBuyerContactLines, formatContractorPopupTitle } from '../invoice/buyerContact.js';

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

test('Sidebar: zawiera etykietę "Zestawienia"', () => {
  const src = readFileSync(
    join(__dir, '../layout/Sidebar.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes("label: 'Zestawienia'"),
    'Sidebar powinien mieć etykietę "Zestawienia"',
  );
  assert.ok(
    !src.includes('Sprzeda\u017c / Zakup'),
    'Sidebar nie powinien mieć starej etykiety "Sprzedaż / Zakup"',
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

test('Topbar: zawiera tytuł "Zestawienia"', () => {
  const src = readFileSync(
    join(__dir, '../layout/Topbar.jsx'),
    'utf-8',
  );
  assert.ok(
    src.includes('>Zestawienia</span>'),
    'Topbar powinien zawierać tytuł "Zestawienia"',
  );
  assert.ok(
    !src.includes('Zestawienia: sprzeda\u017c / zakup'),
    'Topbar nie powinien zawierać starego tytułu z "sprzedaż / zakup"',
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

test('InvoiceCardList: dla zakupów pokazuje numer z KSeF/XML bez sekwencji IFG', () => {
  const src = readFileSync(
    join(__dir, '../invoice/InvoiceCardList.jsx'),
    'utf-8',
  );
  assert.ok(src.includes("direction === 'purchase'"), 'brak gałęzi purchase');
  assert.ok(src.includes('getPurchaseDisplayNumber'), 'brak źródła numeru KSeF (getPurchaseDisplayNumber)');
  assert.ok(src.includes('displayNumber'), 'brak displayNumber dla zakupów');
  assert.ok(src.includes('return b.dateTs - a.dateTs'), 'brak sortowania zakupów po dacie malejąco');
});

test('InvoiceCardList: dla zakupów obcina długi numer w kolumnie (ellipsis + title)', () => {
  const jsxSrc = readFileSync(
    join(__dir, '../invoice/InvoiceCardList.jsx'),
    'utf-8',
  );
  const cssSrc = readFileSync(
    join(__dir, '../invoice/InvoiceCardList.module.css'),
    'utf-8',
  );
  assert.ok(jsxSrc.includes('styles.purchaseNumberColumn'), 'brak klasy purchaseNumberColumn');
  assert.ok(jsxSrc.includes('styles.purchaseNumberValue'), 'brak klasy purchaseNumberValue');
  assert.ok(cssSrc.includes('.purchaseNumberValue'), 'brak stylu purchaseNumberValue');
  assert.ok(cssSrc.includes('text-overflow: ellipsis'), 'brak ellipsis w CSS');
  assert.ok(cssSrc.includes('10ch'), 'brak stałej szerokości 10ch dla numeru zakupu');
  assert.ok(cssSrc.includes('minmax(243px'), 'brak szerszej kolumny Sprzedawca');
  assert.ok(cssSrc.includes('148px'), 'brak szerszej kolumny PDF');
});

test('InvoiceCardList: dla zakupów popup Sprzedawcy zamiast natywnego title', () => {
  const jsxSrc = readFileSync(
    join(__dir, '../invoice/InvoiceCardList.jsx'),
    'utf-8',
  );
  assert.ok(jsxSrc.includes('ContractorNameWithPopup'), 'brak popupu kontrahenta');
  assert.ok(jsxSrc.includes('getContractorSnapshot'), 'brak snapshotu sprzedawcy');
  assert.equal(
    jsxSrc.includes('styles.purchaseSellerValue'),
    false,
    'stary title/ellipsis sprzedawcy powinien być zastąpiony popupem',
  );
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

test('InvoiceList: race condition miesiąca chroniona przez invoice pool key', () => {
  const src = readFileSync(
    join(__dir, '../invoice/InvoiceList.jsx'),
    'utf-8',
  );
  // Po migracji na invoicePool nie ma requestSeqRef — stale response
  // jest odcinany przez osobny poolKey per zestaw filtrów + loadInvoicePool cache.
  assert.ok(src.includes('buildInvoicePoolKey'), 'brak buildInvoicePoolKey');
  assert.ok(src.includes('buildInvoicePoolQuery'), 'brak buildInvoicePoolQuery');
  assert.ok(src.includes('loadInvoicePool'), 'brak loadInvoicePool');
  assert.ok(src.includes('poolKey'), 'brak poolKey wiążącego filtry z pulą');
});

test('InvoiceList: przy filters.month odfiltrowuje pulę po issue_date', () => {
  const src = readFileSync(
    join(__dir, '../invoice/InvoiceList.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('filterInvoicesFromPool'), 'brak filterInvoicesFromPool');
  assert.ok(src.includes('onItemsChange(filteredItems)'), 'onItemsChange powinno dostawać już odfiltrowane elementy');
  assert.ok(src.includes('filteredItems'), 'brak filteredItems');
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

// ── GWO-IFG-0023: YTD + rename + buyer popup ─────────────────────────────────

test('currentYearToDateRange: zakres od 1 stycznia do dziś bez hardcodu roku', () => {
  const now = new Date(2099, 6, 20); // 20 lipca 2099
  const range = currentYearToDateRange(now);
  assert.equal(range.from, '2099-01-01');
  assert.equal(range.to, '2099-07-20');

  const now2 = new Date(2100, 0, 5);
  const range2 = currentYearToDateRange(now2);
  assert.equal(range2.from, '2100-01-01');
  assert.equal(range2.to, '2100-01-05');
});

test('buildYtdBarHeights: wspólna skala proporcjonalna', () => {
  const h = buildYtdBarHeights(200, 100);
  assert.equal(h.salePct, 100);
  assert.equal(h.purchasePct, 50);
  assert.equal(h.max, 200);

  const zero = buildYtdBarHeights(0, 0);
  assert.equal(zero.salePct, 0);
  assert.equal(zero.purchasePct, 0);
});

test('DashboardSummary: panel YTD z paskami sale/purchase', () => {
  const src = readFileSync(join(__dir, './DashboardSummary.jsx'), 'utf-8');
  assert.ok(src.includes('ytdPanel'), 'brak panelu ytdPanel');
  assert.ok(src.includes('currentYearToDateRange'), 'YTD musi używać currentYearToDateRange');
  assert.ok(src.includes('ytdBarSale') && src.includes('ytdBarPurchase'), 'brak klas pasków');
  assert.ok(!/\b2026\b/.test(src), 'DashboardSummary nie powinien hardcodować roku 2026');
});

test('DashboardSummary CSS: kolory pasków żółty/niebieski', () => {
  const src = readFileSync(join(__dir, './DashboardSummary.module.css'), 'utf-8');
  assert.ok(src.includes('.ytdBarSale') && src.includes('#d4a017'), 'pasek sprzedaży żółty');
  assert.ok(src.includes('.ytdBarPurchase') && src.includes('#3b82f6'), 'pasek zakupu niebieski');
  assert.ok(src.includes('.chartsRow'), 'brak layoutu chartsRow');
});

test('DashboardSummary CSS: YTD panel zintegrowany (szerokość i wspólna wysokość)', () => {
  const src = readFileSync(join(__dir, './DashboardSummary.module.css'), 'utf-8');
  assert.ok(src.includes('flex: 0 0 200px') || src.includes('width: 200px'), 'panel YTD powinien mieć ~200px');
  assert.ok(src.includes('min-height: 180px'), 'wspólna wysokość obszaru pasków z wykresem');
  assert.ok(src.includes('font-variant-numeric: tabular-nums'), 'kwoty YTD tabular-nums');
});

test('InvoiceCardList CSS: popup nabywcy z portalem fixed (bez clip overflow)', () => {
  const css = readFileSync(join(__dir, '../invoice/InvoiceCardList.module.css'), 'utf-8');
  const jsx = readFileSync(join(__dir, '../invoice/InvoiceCardList.jsx'), 'utf-8');
  assert.ok(css.includes('.buyerPopupFixed') && css.includes('position: fixed'), 'brak fixed portal CSS');
  assert.ok(jsx.includes('createPortal'), 'popup musi iść przez createPortal');
  assert.ok(jsx.includes('data-buyer-hover-trigger'), 'brak triggera w komórce nabywcy');
  assert.ok(jsx.includes('data-buyer-popup'), 'brak atrybutu data-buyer-popup');
  assert.ok(
    !jsx.includes('Źródło numeru:'),
    'numer faktury nie może mieć technicznego tooltipu Źródło numeru',
  );
  assert.ok(
    !jsx.includes('`Źródło numeru: ${item.numberSource}`'),
    'title nie może ujawniać numberSource',
  );
});

test('extractBuyerContactLines: tylko kontakt, bez NIP/adresu', () => {
  const lines = extractBuyerContactLines({
    name: 'ACME Sp. z o.o.',
    nip: '5250000000',
    street: 'ul. Testowa 1',
    city: 'Warszawa',
    phone: '+48 123 456 789',
    email: 'biuro@acme.example',
  });
  assert.deepEqual(lines, ['+48 123 456 789', 'biuro@acme.example']);
});

test('extractBuyerContactLines: brak kontaktu → pusta lista', () => {
  assert.deepEqual(
    extractBuyerContactLines({ name: 'ACME', nip: '5250000000', city: 'Kraków' }),
    [],
  );
});

test('InvoiceCardList: popup kontrahenta (nabywca i sprzedawca)', () => {
  const src = readFileSync(join(__dir, '../invoice/InvoiceCardList.jsx'), 'utf-8');
  assert.ok(src.includes('ContractorNameWithPopup'), 'brak komponentu popup kontrahenta');
  assert.ok(src.includes('formatContractorPopupTitle'), 'brak tytułu z miejscowością');
  assert.ok(src.includes('getContractorSnapshot'), 'brak wspólnego snapshotu nazwa+city');
  assert.ok(src.includes('extractBuyerContactLines'), 'brak ekstrakcji kontaktu');
});

test('formatContractorPopupTitle: Nazwa, Miejscowość', () => {
  assert.equal(
    formatContractorPopupTitle('ABC Sp. z o.o.', { city: 'Warszawa', street: 'ul. X 1' }),
    'ABC Sp. z o.o., Warszawa',
  );
});
