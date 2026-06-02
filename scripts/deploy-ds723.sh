#!/usr/bin/env bash
# deploy-ds723.sh — wdrożenie brancha production na DS723+.
#
# Wymagania:
#   - SSH alias ds723 (Mac mini → NAS)
#   - Branch lokalny: production (zsynchronizowany z origin)
#   - Frontend budowany TYLKO na Mac mini (rsync dist/ → NAS)
#   - DS723+ nie kompiluje frontendu
#
# Użycie:
#   bash scripts/deploy-ds723.sh
#   SKIP_TESTS=1 bash scripts/deploy-ds723.sh   # tylko w wyjątkowych sytuacjach

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=ds723.env
source "${SCRIPT_DIR}/ds723.env"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
info() { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

BRANCH="$(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD)"
if [[ "${BRANCH}" != "${DS723_DEPLOY_BRANCH}" ]]; then
  error "Deploy tylko z brancha ${DS723_DEPLOY_BRANCH} (jesteś na: ${BRANCH})"
fi

if [[ -n "$(git -C "${REPO_ROOT}" status --porcelain)" ]]; then
  warn "Masz niezatwierdzone zmiany lokalne."
  git -C "${REPO_ROOT}" status --short
  read -r -p "Kontynuować mimo to? [y/N] " ans
  [[ "${ans}" =~ ^[Yy]$ ]] || exit 1
fi

COMMIT="$(git -C "${REPO_ROOT}" rev-parse --short HEAD)"
info "Deploy commit ${COMMIT} → DS723+ (branch ${DS723_DEPLOY_BRANCH})"

if [[ "${SKIP_TESTS:-0}" != "1" ]]; then
  bash "${SCRIPT_DIR}/test-ifg.sh"
else
  warn "SKIP_TESTS=1 — pomijam test-ifg.sh"
fi

info "Buduję frontend-react (Mac mini)..."
(cd "${REPO_ROOT}/frontend-react" && npm run build)

info "Synchronizuję frontend-react/dist/ → NAS (tar przez SSH)..."
tar czf - -C "${REPO_ROOT}/frontend-react/dist" . | \
  ssh -p "${DS723_PORT}" "${DS723_USER}@${DS723_HOST}" \
  "mkdir -p '${DS723_REPO}/frontend-react/dist' && find '${DS723_REPO}/frontend-react/dist' -mindepth 1 -delete && tar xzf - -C '${DS723_REPO}/frontend-react/dist'"

SSH_BASE=(ssh -p "${DS723_PORT}" "${DS723_USER}@${DS723_HOST}")

info "git pull origin ${DS723_DEPLOY_BRANCH} na DS723+..."
"${SSH_BASE[@]}" bash -s <<REMOTE
set -euo pipefail
export PATH="${DS723_DOCKER_PATH}:\$PATH"
cd "${DS723_REPO}"
git fetch origin
git checkout ${DS723_DEPLOY_BRANCH}
git pull origin ${DS723_DEPLOY_BRANCH}
REMOTE

info "docker compose build api..."
"${SSH_BASE[@]}" bash -s <<REMOTE
set -euo pipefail
export PATH="${DS723_DOCKER_PATH}:\$PATH"
cd "${DS723_REPO}"
docker compose -f "${DS723_COMPOSE_FILE}" --env-file "${DS723_ENV_FILE}" build api
REMOTE

info "docker compose up..."
"${SSH_BASE[@]}" bash -s <<REMOTE
set -euo pipefail
export PATH="${DS723_DOCKER_PATH}:\$PATH"
cd "${DS723_REPO}"
docker compose -f "${DS723_COMPOSE_FILE}" --env-file "${DS723_ENV_FILE}" up -d --remove-orphans api worker
REMOTE

info "alembic upgrade head..."
"${SSH_BASE[@]}" bash -s <<REMOTE
set -euo pipefail
export PATH="${DS723_DOCKER_PATH}:\$PATH"
cd "${DS723_REPO}"
docker compose -f "${DS723_COMPOSE_FILE}" --env-file "${DS723_ENV_FILE}" exec -T api alembic upgrade head
REMOTE

info "status kontenerów:"
"${SSH_BASE[@]}" bash -s <<REMOTE
set -euo pipefail
export PATH="${DS723_DOCKER_PATH}:\$PATH"
cd "${DS723_REPO}"
docker compose -f "${DS723_COMPOSE_FILE}" --env-file "${DS723_ENV_FILE}" ps
REMOTE

bash "${SCRIPT_DIR}/healthcheck.sh"
info "Deploy zakończony (commit: ${COMMIT})"
