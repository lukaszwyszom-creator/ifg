import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const filePath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  'InvoiceCardList.jsx',
);
const source = readFileSync(filePath, 'utf8');

test('InvoiceCardList nie generuje ui:temporary_sequence', () => {
  assert.equal(source.includes('ui:temporary_sequence'), false);
  assert.equal(source.includes('temporary_sequence'), false);
});

test('InvoiceCardList formatuje numer z backend number_local', () => {
  assert.ok(source.includes('getSaleDisplayNumber'));
  assert.ok(source.includes('backend:number_local'));
  assert.equal(source.includes('displayNumber: `${pad2(sequence)}'), false);
});
