#!/usr/bin/env bash
# logs-api.sh — tail logów kontenera api na DS723+.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ds723.env
source "${SCRIPT_DIR}/ds723.env"

LINES="${1:-100}"
FOLLOW="${2:---follow}"

ssh -p "${DS723_PORT}" "${DS723_USER}@${DS723_HOST}" bash -s <<REMOTE
set -euo pipefail
export PATH="${DS723_DOCKER_PATH}:\$PATH"
cd "${DS723_REPO}"
docker compose -f "${DS723_COMPOSE_FILE}" --env-file "${DS723_ENV_FILE}" logs ${FOLLOW} --tail=${LINES} api
REMOTE
