import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dir, '..', 'vite.config.js'), 'utf-8');

test('vite config: tryb LAN-safe po porcie 3001 i bez HMR', () => {
  assert.match(source, /devPort === bootstrapBackendPort/);
  assert.match(source, /hmr: lanSafeMode \? false : undefined/);
  assert.match(source, /host: '127\.0\.0\.1'/);
  assert.match(source, /strip-vite-client-lan-safe/);
});

test('vite config: package dev:direct wymusza LAN-safe', () => {
  const pkg = readFileSync(join(__dir, '..', 'package.json'), 'utf-8');
  assert.match(pkg, /"dev:direct": "VITE_BEHIND_BOOTSTRAP=1 PORT=3001 vite"/);
});
