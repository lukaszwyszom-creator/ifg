import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dir, 'dev-bootstrap.mjs'), 'utf-8');

test('dev bootstrap: starts Vite on PORT (default 3000) under /ui/login', () => {
  assert.match(source, /const devPort = Number\(process\.env\.PORT \|\| 3000\);/);
  assert.match(source, /const loginUrl = `http:\/\/127\.0\.0\.1:\$\{devPort\}\/ui\/login`;/);
  assert.match(source, /spawn\(viteBin, \['--host', '0\.0\.0\.0', '--port', String\(devPort\)\]/);
  assert.match(source, /await ensurePortAvailable\(\);\s*startVite\(\);/s);
});

test('dev bootstrap: optional local docker warm-up when API health fails', () => {
  assert.match(source, /function warmBackend\(\)/);
  assert.match(source, /docker\/docker-compose\.yml/);
  assert.match(source, /'up', '-d', 'db', 'api', 'worker'/);
  assert.match(source, /warmBackend\(\);/);
});

test('dev bootstrap: no KeepAlive HTTP proxy / VITE_BEHIND_BOOTSTRAP architecture', () => {
  assert.doesNotMatch(source, /http\.createServer/);
  assert.doesNotMatch(source, /VITE_BEHIND_BOOTSTRAP/);
  assert.doesNotMatch(source, /apiProxy\.web/);
  assert.doesNotMatch(source, /frontendProxy\.ws/);
});

test('dev bootstrap: --restart frees the port before spawn', () => {
  assert.match(source, /process\.argv\.includes\('--restart'\)/);
  assert.match(source, /killPort\(devPort\)/);
});
