import test from 'node:test';
import assert from 'node:assert/strict';
import {
  catalogItemToLineFields,
  grossToNet,
} from './catalogItemLineFromWarehouse.js';

const BASE_ITEM = {
  name: 'Książka',
  isbn: '978-83-123456-7-8',
  unit: 'szt.',
  vat_rate: '23',
};

test('brak mode lub mode=net → unit_price_net', () => {
  const fields = catalogItemToLineFields({
    ...BASE_ITEM,
    suggested_sale_price: '100.00',
    suggested_sale_price_mode: 'net',
  });
  assert.equal(fields.price_mode, 'net');
  assert.equal(fields.unit_price_net, '100.00');
  assert.equal(fields.unit_price_gross, '');
});

test('mode=net + vat 23% przekazuje vat_rate', () => {
  const fields = catalogItemToLineFields({
    ...BASE_ITEM,
    suggested_sale_price: '100.00',
    suggested_sale_price_mode: 'net',
    vat_rate: '23',
  });
  assert.equal(fields.vat_rate, '23');
  assert.equal(fields.unit_price_net, '100.00');
  assert.equal(fields.price_mode, 'net');
});

test('historyczny brak suggested_sale_price_mode → unit_price_net', () => {
  const fields = catalogItemToLineFields({
    ...BASE_ITEM,
    suggested_sale_price: '100.00',
  });
  assert.equal(fields.unit_price_net, '100.00');
  assert.equal(fields.price_mode, 'net');
});

test('mode=gross → unit_price_gross gdy formularz obsługuje brutto', () => {
  const fields = catalogItemToLineFields({
    ...BASE_ITEM,
    suggested_sale_price: '123.00',
    suggested_sale_price_mode: 'gross',
  });
  assert.equal(fields.price_mode, 'gross');
  assert.equal(fields.unit_price_gross, '123.00');
  assert.equal(fields.unit_price_net, '');
});

test('mode=gross bez obsługi brutto → przeliczenie na netto', () => {
  const fields = catalogItemToLineFields(
    {
      ...BASE_ITEM,
      suggested_sale_price: '123.00',
      suggested_sale_price_mode: 'gross',
    },
    { supportsGrossMode: false },
  );
  assert.equal(fields.price_mode, 'net');
  assert.equal(fields.unit_price_net, grossToNet('123.00', '23'));
});

test('mode=gross + vat 5% bez obsługi brutto → przeliczenie netto', () => {
  const fields = catalogItemToLineFields(
    {
      ...BASE_ITEM,
      suggested_sale_price: '105.00',
      suggested_sale_price_mode: 'gross',
      vat_rate: '5',
    },
    { supportsGrossMode: false },
  );
  assert.equal(fields.price_mode, 'net');
  assert.equal(fields.unit_price_net, '100.00');
});

test('mode=gross + vat 0% bez obsługi brutto → netto = brutto', () => {
  const fields = catalogItemToLineFields(
    {
      ...BASE_ITEM,
      suggested_sale_price: '100.00',
      suggested_sale_price_mode: 'gross',
      vat_rate: '0',
    },
    { supportsGrossMode: false },
  );
  assert.equal(fields.price_mode, 'net');
  assert.equal(fields.unit_price_net, '100.00');
});

test('fallback default_price_net pozostaje netto', () => {
  const fields = catalogItemToLineFields({
    ...BASE_ITEM,
    default_price_net: '20.00',
  });
  assert.equal(fields.unit_price_net, '20.00');
  assert.equal(fields.price_mode, 'net');
});
