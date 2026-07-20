/**
 * Regresja GWO-IFG-0027 — binding hover popupu nabywcy vs tooltip numeru.
 * Uruchamianie: node --test src/components/invoice/invoiceCardListBuyerPopup.test.js
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { extractBuyerContactLines } from './buyerContact.js';

const __dir = dirname(fileURLToPath(import.meta.url));
const jsx = readFileSync(join(__dir, 'InvoiceCardList.jsx'), 'utf-8');
const css = readFileSync(join(__dir, 'InvoiceCardList.module.css'), 'utf-8');

test('numer faktury sprzedaży nie ma technicznego tooltipu numberSource', () => {
  assert.equal(jsx.includes('Źródło numeru:'), false);
  assert.equal(jsx.includes('${item.numberSource}'), false);
  // title tylko dla purchase (pełna nazwa wyświetlanego numeru), nie dla sale
  assert.ok(jsx.includes("direction === 'purchase' && item.displayNumber !== 'brak numeru'"));
});

test('trigger popupu jest w komórce nabywcy (sale)', () => {
  assert.ok(jsx.includes('invoiceCellBuyer'));
  assert.ok(jsx.includes("direction === 'sale'"));
  assert.ok(jsx.includes('BuyerNameWithPopup'));
  assert.ok(jsx.includes('data-buyer-hover-trigger="true"'));
  const dataBuyerStart = jsx.indexOf('<div className={`${styles.cell} ${styles.invoiceCellBuyer}`}>');
  assert.ok(dataBuyerStart > 0, 'brak komórki danych nabywcy');
  const dataBuyerBlock = jsx.slice(
    dataBuyerStart,
    jsx.indexOf('<div className={`${styles.cell} ${styles.invoiceCellNip}`}>', dataBuyerStart),
  );
  assert.ok(dataBuyerBlock.includes('BuyerNameWithPopup'));
  assert.ok(dataBuyerBlock.includes('buyer_snapshot'));
  assert.ok(dataBuyerBlock.includes("direction === 'sale'"));
});

test('popup renderuje nazwę właściwego kontrahenta (+ kontakt bez NIP)', () => {
  assert.ok(jsx.includes('buyerPopupName'));
  assert.ok(jsx.includes('createPortal'));
  assert.ok(css.includes('buyerPopupFixed'));
  const lines = extractBuyerContactLines({
    name: 'ACME Sp. z o.o.',
    nip: '5250000000',
    street: 'ul. Test 1',
    phone: '+48 111',
    email: 'a@b.c',
  });
  assert.deepEqual(lines, ['+48 111', 'a@b.c']);
  assert.ok(!lines.some((l) => l.includes('525')));
});
