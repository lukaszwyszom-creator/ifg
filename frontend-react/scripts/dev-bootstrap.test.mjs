import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dir, 'dev-bootstrap.mjs'), 'utf-8');

test('dev bootstrap: HTTP handler czeka tylko na frontend, backend rozgrzewa w tle', () => {
  assert.match(source, /function warmServices\(\) \{\s+void ensureServices\(\);\s+\}/s);
  assert.match(source, /const server = http\.createServer\(async \(req, res\) => \{\s+warmServices\(\);\s+\s+const frontendReady = await ensureFrontend\(\);/s);
  assert.doesNotMatch(source, /const server = http\.createServer\(async \(req, res\) => \{\s+const ready = await ensureServices\(\);/s);
});