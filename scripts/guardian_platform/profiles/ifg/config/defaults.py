from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[4]
REPO_ROOT = Path(__file__).resolve().parents[5]


def ensure_scripts_path() -> None:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))


def resolve_remote_host(cli_host: str | None = None) -> str:
    if cli_host:
        return cli_host
    return os.environ.get("IFG_DS723_HOST", DEFAULT_REMOTE_HOST)


DEFAULT_REMOTE_HOST = "ds723"
DEFAULT_REMOTE_PATH = "/volume1/docker/ifg_v2/ifg_standalone"
TARGET_BRANCH = "production"
COMPOSE_FILE = "docker/docker-compose.prod.yml"
REQUIRED_COMPOSE_SERVICES = ("api", "worker", "db")

FRONTEND_SRC_PREFIX = "frontend-react/src"
FRONTEND_DIST_STALE_MSG = "Frontend dist wymaga przebudowy (npm run build)."

KSEF_CONNECT_JS_MARKERS = ("openSessionOnce", "openSession: (nip) => openSessionOnce(nip)")
KSEF_CONNECT_TILE_MARKERS = ("actionInFlightRef", "response?.status === 409")
KSEF_CONNECT_DIST_MARKERS = (
    "KSeFConnectionTile.connect",
    "Sesja KSeF jest już aktywna",
)

REPORTS_DIR = REPO_ROOT / "docs" / "guardian"

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
