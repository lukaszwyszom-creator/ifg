import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buyerAddressIncompleteMessage,
  canBuildAdresL1,
  formatAdresL1,
  missingAdresL1Hints,
  shouldShowBuyerAddressEditor,
} from './partyAddress.js';

test('A full REGON → AdresL1 PASS and editor visible', () => {
  const snap = {
    street: 'ul. Testowa',
    building_no: '10',
    postal_code: '00-001',
    city: 'Warszawa',
  };
  assert.equal(canBuildAdresL1(snap), true);
  assert.equal(formatAdresL1(snap), 'ul. Testowa 10, 00-001 Warszawa');
  assert.equal(shouldShowBuyerAddressEditor({ buyerInfo: { id: 1 }, buyerAddress: snap }), true);
});

test('B incomplete REGON → locality visible, editor visible, KSeF blocked', () => {
  const snap = { postal_code: '98-331', city: 'Prusicko' };
  assert.equal(canBuildAdresL1(snap), false);
  assert.deepEqual(missingAdresL1Hints(snap), [
    'ulicę/miejscowość z numerem albo sam nr budynku',
  ]);
  assert.equal(
    shouldShowBuyerAddressEditor({
      buyerNip: '5741680143',
      buyerAddress: snap,
    }),
    true,
  );
  assert.match(buyerAddressIncompleteMessage(snap), /Adres nabywcy/);
});

test('C manual building_no → AdresL1 PASS', () => {
  const snap = {
    postal_code: '98-331',
    city: 'Prusicko',
    building_no: '10',
  };
  assert.equal(canBuildAdresL1(snap), true);
  assert.equal(formatAdresL1(snap), 'Prusicko 10, 98-331 Prusicko');
  assert.deepEqual(missingAdresL1Hints(snap), []);
});

test('D override-shaped address used when contractor base incomplete', () => {
  const effective = {
    street: '',
    building_no: '2',
    postal_code: '98-331',
    city: 'Prusicko',
  };
  assert.equal(canBuildAdresL1(effective), true);
  assert.equal(shouldShowBuyerAddressEditor({ buyerInfo: { id: 'x' }, buyerAddress: effective }), true);
});

test('E place name as street without requiring street null check', () => {
  assert.equal(
    formatAdresL1({
      street: 'Moczydła',
      building_no: '2',
      postal_code: '98-331',
      city: 'Prusicko',
    }),
    'Moczydła 2, 98-331 Prusicko',
  );
  assert.equal(
    canBuildAdresL1({
      street: 'Moczydła',
      building_no: '2',
      postal_code: '98-331',
      city: 'Prusicko',
    }),
    true,
  );
});

test('F truly insufficient address → BLOCK', () => {
  assert.equal(canBuildAdresL1({}), false);
  assert.equal(canBuildAdresL1({ city: 'Prusicko' }), false);
  assert.ok(missingAdresL1Hints({ city: 'Prusicko' }).length >= 1);
});

test('G seller-style snapshot without AdresL1 helper still has locality+street fields', () => {
  // Seller flow uses separate UI logic; AdresL1 helper must not require street alone.
  assert.equal(
    canBuildAdresL1({
      street: 'ul. A',
      building_no: '1',
      postal_code: '00-001',
      city: 'Warszawa',
    }),
    true,
  );
});

test('editor visible for NIP=10 even before buyerInfo arrives', () => {
  assert.equal(
    shouldShowBuyerAddressEditor({
      buyerInfo: null,
      buyerNip: '5741680143',
      buyerAddress: { postal_code: '98-331', city: 'Prusicko' },
    }),
    true,
  );
});

test('literal None/null street does not leak into AdresL1', () => {
  assert.equal(
    formatAdresL1({
      street: 'None',
      building_no: '10',
      postal_code: '98-331',
      city: 'Prusicko',
    }),
    'Prusicko 10, 98-331 Prusicko',
  );
});
