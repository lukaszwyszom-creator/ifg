import test from 'node:test';
import assert from 'node:assert/strict';
import { canBuildAdresL1, formatAdresL1 } from './partyAddress.js';

test('standard street address → AdresL1', () => {
  const snap = {
    street: 'ul. Testowa',
    building_no: '10',
    postal_code: '00-001',
    city: 'Warszawa',
  };
  assert.equal(formatAdresL1(snap), 'ul. Testowa 10, 00-001 Warszawa');
  assert.equal(canBuildAdresL1(snap), true);
});

test('village without street → AdresL1 uses city + building', () => {
  const snap = {
    street: '',
    building_no: '10',
    postal_code: '98-331',
    city: 'Prusicko',
  };
  assert.equal(formatAdresL1(snap), 'Prusicko 10, 98-331 Prusicko');
  assert.equal(canBuildAdresL1(snap), true);
});

test('place name as street → AdresL1', () => {
  assert.equal(
    formatAdresL1({
      street: 'Moczydła',
      building_no: '2',
      postal_code: '98-331',
      city: 'Prusicko',
    }),
    'Moczydła 2, 98-331 Prusicko',
  );
});

test('postal+city only without place line → BLOCK', () => {
  assert.equal(
    canBuildAdresL1({
      postal_code: '98-331',
      city: 'Prusicko',
    }),
    false,
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
