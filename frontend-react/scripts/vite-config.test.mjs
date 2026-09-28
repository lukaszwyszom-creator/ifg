import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dir, '..', 'vite.config.js'), 'utf-8');
const pkg = readFileSync(join(__dir, '..', 'package.json'), 'utf-8');

test('vite config: frontend listens on 0.0.0.0 with PORT default 3000', () => {
  assert.match(source, /const devPort = Number\(process\.env\.PORT \|\| 3000\);/);
  assert.match(source, /host: '0\.0\.0\.0'/);
  assert.match(source, /port: devPort/);
  assert.match(source, /base: '\/ui\/'/);
});

test('vite config: proxies /api and redirects non-/ui paths', () => {
  assert.match(source, /name: 'ui-path-redirect'/);
  assert.match(source, /'\/api'/);
  assert.match(source, /target: devApiTarget/);
});

test('package.json: manual SSD workflows (no KeepAlive LaunchAgent contract)', () => {
  assert.match(pkg, /"dev": "vite --host 0\.0\.0\.0 --port 3000"/);
  assert.match(pkg, /"dev:bootstrap": "node \.\/scripts\/dev-bootstrap\.mjs"/);
  assert.match(pkg, /"dev:direct": "vite --host 0\.0\.0\.0 --port 3000"/);
  assert.match(pkg, /"dev:restart": "lsof -ti :3000 \| xargs kill -9; vite --host 0\.0\.0\.0 --port 3000"/);
  assert.doesNotMatch(pkg, /VITE_BEHIND_BOOTSTRAP=1 PORT=3001/);
});
