/**
 * Czyste funkcje agregacji dla widoku Zestawienia.
 * Bez zależności od React — importowalne w testach node:test.
 */

/**
 * Agreguje faktury PLN (wyklucza rejected i waluty obce).
 * Zwraca { netto, vat, brutto } zaokrąglone do 2 miejsc.
 *
 * Statusy agregowane: accepted, ready_for_submission, sending
 * (wszystkie oprócz rejected — każda wystawiona faktura jest liczona).
 *
 * @param {Array} invoices
 * @returns {{ netto: number, vat: number, brutto: number }}
 */
export function buildPlnSummary(invoices) {
  let netto = 0;
  let vat = 0;
  let brutto = 0;
  for (const inv of invoices) {
    if ((inv.status ?? '') === 'rejected') continue;
    if ((inv.currency ?? 'PLN').toUpperCase() !== 'PLN') continue;
    netto  += parseFloat(inv.total_net   ?? 0) || 0;
    vat    += parseFloat(inv.total_vat   ?? 0) || 0;
    brutto += parseFloat(inv.total_gross ?? 0) || 0;
  }
  return {
    netto:  +netto.toFixed(2),
    vat:    +vat.toFixed(2),
    brutto: +brutto.toFixed(2),
  };
}

/**
 * Wspólna skala wysokości pasków YTD (0–100).
 * Oba paski używają tego samego maksimum (max sale/purchase).
 */
export function buildYtdBarHeights(saleNetto, purchaseNetto) {
  const sale = Math.max(0, Number(saleNetto) || 0);
  const purchase = Math.max(0, Number(purchaseNetto) || 0);
  const max = Math.max(sale, purchase);
  if (max <= 0) {
    return { salePct: 0, purchasePct: 0, max };
  }
  return {
    salePct: (sale / max) * 100,
    purchasePct: (purchase / max) * 100,
    max,
  };
}
