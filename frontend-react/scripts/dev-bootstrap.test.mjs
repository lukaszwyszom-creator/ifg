import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dir, 'dev-bootstrap.mjs'), 'utf-8');

test('dev bootstrap: HTTP handler czeka tylko na frontend, backend rozgrzewa w tle', () => {
  assert.match(source, /function warmServices\(\) \{\s+void ensureServices\(\);\s+\}/s);
  assert.match(source, /const server = http\.createServer\(async \(req, res\) => \{\s+warmServices\(\);\s+\s+const requestPath = req\.url/s);
  assert.match(source, /const frontendReady = await ensureFrontend\(\);/);
  assert.doesNotMatch(source, /const server = http\.createServer\(async \(req, res\) => \{\s+const ready = await ensureServices\(\);/s);
});

test('dev bootstrap: sprawdza gotowość pod ścieżką zgodną z basename /ui', () => {
  assert.match(source, /const frontendReadyPath = '\/ui\/login';/);
  assert.match(source, /function isLanSafeLoginHtml\(html\)/);
  assert.match(source, /!html\.includes\('@vite\/client'\)/);
});

test('dev bootstrap: przekierowuje stare lokalne ścieżki na /ui', () => {
  assert.match(source, /function normalizeUiPath\(requestPath\) \{/);
  assert.match(source, /return `\/ui\$\{requestPath\.startsWith\('\/'\) \? requestPath : `\/\$\{requestPath\}`\}`;/);
  assert.match(source, /res\.writeHead\(302, \{ Location: targetPath, 'Cache-Control': 'no-store' \}\);/);
});

test('dev bootstrap: API idzie bezpośrednio do backendu, Vite wyłącza HMR za proxy', () => {
  assert.match(source, /if \(requestPath\.startsWith\('\/api'\)\)/);
  assert.match(source, /apiProxy\.web\(req, res\)/);
  assert.match(source, /VITE_BEHIND_BOOTSTRAP: '1'/);
  assert.doesNotMatch(source, /frontendProxy\.ws\(/);
  assert.match(source, /restartDevServers\(\)/);
});
