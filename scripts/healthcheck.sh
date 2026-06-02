#!/usr/bin/env bash
# healthcheck.sh — status kontenerów i endpoint /health na DS723+.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ds723.env
source "${SCRIPT_DIR}/ds723.env"

echo "[healthcheck] docker ps:"
ssh -p "${DS723_PORT}" "${DS723_USER}@${DS723_HOST}" bash -s <<REMOTE
set -euo pipefail
export PATH="${DS723_DOCKER_PATH}:\$PATH"
cd "${DS723_REPO}"
docker compose -f "${DS723_COMPOSE_FILE}" --env-file "${DS723_ENV_FILE}" ps
REMOTE

echo
echo "[healthcheck] GET /health:"
ssh -p "${DS723_PORT}" "${DS723_USER}@${DS723_HOST}" \
  "curl -fsS http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null || curl -fsS http://127.0.0.1:8000/health"
