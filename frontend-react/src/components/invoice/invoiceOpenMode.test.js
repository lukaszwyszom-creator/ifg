import test from 'node:test';
import assert from 'node:assert/strict';
import { getInvoiceOpenMode, isInvoiceEditable, resolveKsefState } from './invoiceOpenMode.js';

test('status wysylki pozwala na edycje', () => {
  assert.equal(resolveKsefState('ready_for_submission').label, 'Wyślij');
  assert.equal(isInvoiceEditable('ready_for_submission'), true);
  assert.equal(getInvoiceOpenMode('ready_for_submission'), 'edit');
});

test('status odrzucona pozwala na edycje', () => {
  assert.equal(resolveKsefState('rejected').label, 'Odrzucona');
  assert.equal(isInvoiceEditable('rejected'), true);
  assert.equal(getInvoiceOpenMode('rejected'), 'edit');
});

test('status analiza blokuje edycje i wymusza podglad', () => {
  assert.equal(resolveKsefState('sending').label, 'Analiza');
  assert.equal(isInvoiceEditable('sending'), false);
  assert.equal(getInvoiceOpenMode('sending'), 'preview');
});

test('status zaakceptowana blokuje edycje i wymusza podglad', () => {
  // ACCEPTED jest nieedytowalny - tylko podgląd
  assert.equal(isInvoiceEditable('accepted'), false);
  assert.equal(getInvoiceOpenMode('accepted'), 'preview');
});

test('klikniecie faktury wybiera tryb na podstawie statusu', () => {
  const modes = [
    getInvoiceOpenMode('ready_for_submission'),
    getInvoiceOpenMode('rejected'),
    getInvoiceOpenMode('sending'),
    getInvoiceOpenMode('accepted'),
  ];

  assert.deepEqual(modes, ['edit', 'edit', 'preview', 'preview']);
});
