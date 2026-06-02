#!/usr/bin/env bash
# test-ifg.sh — testy przed merge/deploy (Mac mini).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[test-ifg] backend: pytest tests/unit"
cd "${REPO_ROOT}"
PYTHON="python3"
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
fi
"${PYTHON}" -m pytest tests/unit -q

echo "[test-ifg] frontend: npm run build"
cd "${REPO_ROOT}/frontend-react"
npm run build

echo "[test-ifg] OK"
