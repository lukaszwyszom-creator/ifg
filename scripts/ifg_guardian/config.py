from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TARGET_BRANCH = "production"
DEFAULT_REMOTE_HOST = "ds723"
DEFAULT_REMOTE_PATH = "/volume1/docker/ifg_v2/ifg_standalone"
REQUIRED_COMPOSE_SERVICES = ("api", "worker", "db")
COMPOSE_FILE = "docker/docker-compose.prod.yml"

MOBILE_API_GLOB = "mobile-expo/src/api/**/*.ts"
ROUTER_GLOB = "app/api/routers/**/*.py"
MAIN_FILE = ROOT / "app" / "main.py"

FRONTEND_SRC_PREFIX = "frontend-react/src"
FRONTEND_DIST_STALE_MSG = "Frontend dist wymaga przebudowy (npm run build)."

KSEF_CONNECT_JS_MARKERS = ("openSessionOnce", "openSession: (nip) => openSessionOnce(nip)")
KSEF_CONNECT_TILE_MARKERS = ("actionInFlightRef", "response?.status === 409")
KSEF_CONNECT_DIST_MARKERS = (
    "KSeFConnectionTile.connect",
    "Sesja KSeF jest już aktywna",
)

REPORTS_DIR = ROOT / "docs" / "guardian"

# Patterns treated as gitignore-like (should not be committed)
IGNORE_PATTERNS = (
    "frontend-react/dist/",
    ".env",
    ".env.production",
    ".env.staging",
    "node_modules/",
    ".venv/",
    "__pycache__/",
    ".DS_Store",
)
