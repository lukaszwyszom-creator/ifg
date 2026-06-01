import { spawn, execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import process from 'node:process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, '..');
const rootDir = path.resolve(frontendDir, '..');
const devPort = Number(process.env.PORT || 3000);
const loginUrl = `http://127.0.0.1:${devPort}/ui/login`;
const backendHealthUrl = process.env.VITE_DEV_API_TARGET
  ? `${process.env.VITE_DEV_API_TARGET.replace(/\/$/, '')}/health`
  : 'http://127.0.0.1:8000/health';
const viteBin = path.join(frontendDir, 'node_modules', '.bin', 'vite');

const shouldRestart = process.argv.includes('--restart');

function log(message) {
  process.stdout.write(`[dev-bootstrap] ${message}\n`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function killPort(port) {
  try {
    execSync(`lsof -ti :${port} | xargs kill -9`, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function isPortInUse(port) {
  try {
    execSync(`lsof -ti :${port}`, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

async function isViteReady() {
  try {
    const response = await fetch(loginUrl, { redirect: 'manual' });
    return response.status >= 200 && response.status < 400;
  } catch {
    return false;
  }
}

async function ensurePortAvailable() {
  if (shouldRestart) {
    log(`Restart: zabijam procesy na porcie ${devPort}...`);
    killPort(devPort);
    await sleep(1000);
    return;
  }

  if (!isPortInUse(devPort)) {
    return;
  }

  if (await isViteReady()) {
    log(`Vite już działa: ${loginUrl}`);
    log('Użyj npm run dev:restart aby wymusić restart.');
    process.exit(0);
  }

  log(`Port ${devPort} zajęty przez niedziałający proces — zabijam...`);
  killPort(devPort);
  await sleep(500);
}

function warmBackend() {
  void (async () => {
    try {
      const response = await fetch(backendHealthUrl, { redirect: 'manual' });
      if (response.status >= 200 && response.status < 400) {
        return;
      }
    } catch {
      // backend offline — spróbuj podnieść docker w tle
    }

    log('Backend offline — uruchamiam docker compose w tle...');
    spawn('docker', ['compose', '-f', 'docker/docker-compose.yml', 'up', '-d', 'db', 'api', 'worker'], {
      cwd: rootDir,
      detached: true,
      stdio: 'ignore',
    }).unref();
  })();
}

function startVite() {
  log(`Uruchamiam Vite: http://0.0.0.0:${devPort}/ui/login`);
  warmBackend();

  const child = spawn(viteBin, ['--host', '0.0.0.0', '--port', String(devPort)], {
    cwd: frontendDir,
    stdio: 'inherit',
    env: process.env,
  });

  child.on('error', (error) => {
    log(`Nie udało się uruchomić Vite: ${error.message}`);
    process.exit(1);
  });

  child.on('exit', (code, signal) => {
    if (signal) {
      process.exit(1);
    }
    process.exit(code ?? 0);
  });
}

await ensurePortAvailable();
startVite();
