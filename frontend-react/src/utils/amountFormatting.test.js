import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { formatAmountByCurrency, formatCurrencyPLN } from './amountFormatting.js';

const __dir = dirname(fileURLToPath(import.meta.url));

const CASES = [
  [0, '0,00 zł'],
  [1, '1,00 zł'],
  [12.3, '12,30 zł'],
  [999.99, '999,99 zł'],
  [1000, '1 000,00 zł'],
  [123456.7, '123 456,70 zł'],
  [1234567.89, '1 234 567,89 zł'],
];

test('formatCurrencyPLN: format xxx xxx,xx zł', () => {
  for (const [value, expected] of CASES) {
    assert.equal(formatCurrencyPLN(value), expected);
  }
});

test('formatAmountByCurrency: PLN/EUR/USD/inna', () => {
  assert.equal(formatAmountByCurrency(123456.7, 'PLN'), '123 456,70 zł');
  assert.equal(formatAmountByCurrency(123456.7, 'EUR'), '123 456,70 €');
  assert.equal(formatAmountByCurrency(123456.7, 'USD'), '123 456,70 $');
  assert.equal(formatAmountByCurrency(123456.7, 'GBP'), '123 456,70 GBP');
});

test('InvoiceCardList: używa formatAmountByCurrency z invoice.currency', () => {
  const src = readFileSync(
    join(__dir, '../components/invoice/InvoiceCardList.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('formatAmountByCurrency'), 'brak użycia formatAmountByCurrency');
  assert.ok(src.includes('invoice.currency'), 'brak przekazania invoice.currency');
});

test('OpenInvoicesPanel: wiersze faktur używają waluty dokumentu', () => {
  const src = readFileSync(
    join(__dir, '../pages/advanced/OpenInvoicesPanel.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('formatAmountByCurrency'), 'brak użycia formatAmountByCurrency w OpenInvoicesPanel');
  assert.ok(src.includes("invoice.currency || 'PLN'"), 'brak fallbacku do currency dokumentu');
});

test('PaymentsPage: kwota transakcji używa row.currency', () => {
  const src = readFileSync(
    join(__dir, '../pages/payments/PaymentsPage.jsx'),
    'utf-8',
  );
  assert.ok(src.includes('formatAmountByCurrency'), 'brak użycia formatAmountByCurrency w PaymentsPage');
  assert.ok(src.includes('row.currency'), 'brak waluty transakcji w formatterze');
});
