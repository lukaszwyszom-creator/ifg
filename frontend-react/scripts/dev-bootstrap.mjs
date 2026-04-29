import http from 'node:http';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import process from 'node:process';
import httpProxy from 'http-proxy';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, '..');
const rootDir = path.resolve(frontendDir, '..');
const publicPort = 3000;
const frontendPort = 3001;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const backendHealthUrl = 'http://127.0.0.1:8000/health';

let frontendStartPromise = null;
let backendStartPromise = null;

const proxy = httpProxy.createProxyServer({
  target: frontendUrl,
  ws: true,
  changeOrigin: true,
});

proxy.on('error', (_error, req, res) => {
  void ensureServices();

  if (res && !res.headersSent) {
    res.writeHead(503, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(renderBootPage(req?.url || '/login'));
  }
});

function log(message) {
  process.stdout.write(`[dev-bootstrap] ${message}\n`);
}

async function fetchOk(url) {
  try {
    const response = await fetch(url, { redirect: 'manual' });
    return response.status >= 200 && response.status < 400;
  } catch {
    return false;
  }
}

async function isFrontendReady() {
  return fetchOk(`${frontendUrl}/login`);
}

async function isBackendReady() {
  return fetchOk(backendHealthUrl);
}

async function waitForReady(checkFn, timeoutMs) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    if (await checkFn()) {
      return true;
    }

    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  return false;
}

function spawnDetached(command, args, options) {
  const child = spawn(command, args, {
    ...options,
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
}

async function ensureFrontend() {
  if (await isFrontendReady()) {
    return true;
  }

  if (!frontendStartPromise) {
    frontendStartPromise = (async () => {
      log('Uruchamiam frontend dev server na porcie 3001...');
      spawnDetached('npm', ['run', 'dev:direct'], {
        cwd: frontendDir,
        env: {
          ...process.env,
          PORT: String(frontendPort),
        },
      });

      return waitForReady(isFrontendReady, 30000);
    })().finally(() => {
      frontendStartPromise = null;
    });
  }

  return frontendStartPromise;
}

async function ensureBackend() {
  if (await isBackendReady()) {
    return true;
  }

  if (!backendStartPromise) {
    backendStartPromise = (async () => {
      log('Uruchamiam backend docker compose...');
      spawnDetached('docker', ['compose', '-f', 'docker/docker-compose.yml', 'up', '-d', 'db', 'api', 'worker'], {
        cwd: rootDir,
        env: process.env,
      });

      return waitForReady(isBackendReady, 120000);
    })().finally(() => {
      backendStartPromise = null;
    });
  }

  return backendStartPromise;
}

async function ensureServices() {
  const [frontendReady, backendReady] = await Promise.all([
    ensureFrontend(),
    ensureBackend(),
  ]);
  return frontendReady && backendReady;
}

function renderBootPage(requestPath) {
  const safePath = requestPath || '/login';
  return `<!DOCTYPE html>
<html lang="pl">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Uruchamianie IFG dev</title>
    <style>
      body {
        margin: 0;
        font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: radial-gradient(circle at top, #20344a 0%, #09131d 55%, #04080d 100%);
        color: #f4efe6;
        min-height: 100vh;
        display: grid;
        place-items: center;
      }
      main {
        width: min(560px, calc(100vw - 48px));
        padding: 32px;
        border-radius: 24px;
        background: rgba(9, 19, 29, 0.82);
        border: 1px solid rgba(214, 170, 85, 0.28);
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.4);
      }
      h1 {
        margin: 0 0 12px;
        font-size: 28px;
      }
      p {
        margin: 0;
        line-height: 1.55;
        color: #d8d1c4;
      }
      .dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: #d6aa55;
        margin-right: 10px;
        animation: pulse 1.2s infinite ease-in-out;
      }
      @keyframes pulse {
        0%, 100% { transform: scale(0.75); opacity: 0.45; }
        50% { transform: scale(1); opacity: 1; }
      }
    </style>
  </head>
  <body>
    <main>
      <h1><span class="dot"></span>Uruchamianie środowiska dev</h1>
      <p>Sprawdzam backend i frontend. Gdy oba będą gotowe, strona logowania otworzy się automatycznie.</p>
    </main>
    <script>
      window.setTimeout(() => window.location.replace(${JSON.stringify(safePath)}), 1500);
    </script>
  </body>
</html>`;
}

const server = http.createServer(async (req, res) => {
  const ready = await ensureServices();

  if (!ready) {
    res.writeHead(503, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(renderBootPage(req.url));
    return;
  }

  proxy.web(req, res);
});

server.on('upgrade', async (req, socket, head) => {
  const frontendReady = await isFrontendReady();
  if (!frontendReady) {
    void ensureFrontend();
    socket.destroy();
    return;
  }
  proxy.ws(req, socket, head);
});

server.listen(publicPort, '0.0.0.0', () => {
  log(`Bootstrap nasłuchuje na http://127.0.0.1:${publicPort}`);
  void ensureServices();
});