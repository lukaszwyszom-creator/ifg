/**
 * Regresja GWO-IFG-0027/0028 — popup kontrahenta (nabywca/sprzedawca) + miejscowość.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { extractBuyerContactLines, formatContractorPopupTitle } from './buyerContact.js';

const __dir = dirname(fileURLToPath(import.meta.url));
const jsx = readFileSync(join(__dir, 'InvoiceCardList.jsx'), 'utf-8');
const css = readFileSync(join(__dir, 'InvoiceCardList.module.css'), 'utf-8');

test('numer faktury sprzedaży nie ma technicznego tooltipu numberSource', () => {
  assert.equal(jsx.includes('Źródło numeru:'), false);
  assert.equal(jsx.includes('${item.numberSource}'), false);
  assert.ok(jsx.includes("direction === 'purchase' && item.displayNumber !== 'brak numeru'"));
});

test('trigger popupu jest w komórce kontrahenta (sale i purchase)', () => {
  assert.ok(jsx.includes('ContractorNameWithPopup'));
  assert.ok(jsx.includes('getContractorSnapshot'));
  assert.ok(jsx.includes('data-contractor-hover-trigger="true"'));
  const dataBuyerStart = jsx.indexOf('<div className={`${styles.cell} ${styles.invoiceCellBuyer}`}>');
  assert.ok(dataBuyerStart > 0, 'brak komórki danych kontrahenta');
  const dataBuyerBlock = jsx.slice(
    dataBuyerStart,
    jsx.indexOf('<div className={`${styles.cell} ${styles.invoiceCellNip}`}>', dataBuyerStart),
  );
  assert.ok(dataBuyerBlock.includes('ContractorNameWithPopup'));
  assert.ok(dataBuyerBlock.includes('getContractorSnapshot'));
  assert.equal(dataBuyerBlock.includes("direction === 'sale'"), false, 'popup nie może być tylko dla sale');
});

test('popup renderuje nazwę z miejscowością (bez ulicy/NIP)', () => {
  assert.ok(jsx.includes('formatContractorPopupTitle'));
  assert.ok(jsx.includes('createPortal'));
  assert.ok(css.includes('buyerPopupFixed'));
  const title = formatContractorPopupTitle('ABC Sp. z o.o.', {
    name: 'ABC Sp. z o.o.',
    city: 'Warszawa',
    street: 'ul. Test 1',
    postal_code: '00-001',
    nip: '5250000000',
  });
  assert.equal(title, 'ABC Sp. z o.o., Warszawa');
  assert.ok(!title.includes('ul.'));
  assert.ok(!title.includes('00-001'));
  assert.ok(!title.includes('525'));

  const lines = extractBuyerContactLines({
    name: 'ACME Sp. z o.o.',
    nip: '5250000000',
    street: 'ul. Test 1',
    city: 'Warszawa',
    phone: '+48 111',
    email: 'a@b.c',
  });
  assert.deepEqual(lines, ['+48 111', 'a@b.c']);
});
