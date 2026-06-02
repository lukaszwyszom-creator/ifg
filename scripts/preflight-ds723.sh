#!/usr/bin/env bash
# preflight-ds723.sh — kontrola gotowości DS723+ przed/po deployu.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=ds723.env
source "${SCRIPT_DIR}/ds723.env"

FAIL=0
ok() { echo "[preflight] OK  $*"; }
bad() { echo "[preflight] FAIL $*"; FAIL=1; }

echo "[preflight] lokalny branch:"
LOCAL_BRANCH="$(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD)"
echo "  ${LOCAL_BRANCH}"
if [[ "${LOCAL_BRANCH}" != "${DS723_DEPLOY_BRANCH}" ]]; then
  bad "lokalny branch powinien być ${DS723_DEPLOY_BRANCH}"
else
  ok "branch ${DS723_DEPLOY_BRANCH}"
fi

echo "[preflight] zdalny branch + commit:"
REMOTE_INFO="$(ssh -p "${DS723_PORT}" "${DS723_USER}@${DS723_HOST}" bash -s <<REMOTE
cd "${DS723_REPO}" || exit 1
echo "branch=\$(git branch --show-current)"
echo "commit=\$(git rev-parse --short HEAD)"
REMOTE
)"
echo "  ${REMOTE_INFO//[$'\n']/ | }"
if [[ "${REMOTE_INFO}" != *"branch=${DS723_DEPLOY_BRANCH}"* ]]; then
  bad "DS723+ nie jest na branchu ${DS723_DEPLOY_BRANCH}"
else
  ok "DS723+ na ${DS723_DEPLOY_BRANCH}"
fi

echo "[preflight] REGON_API_KEY w .env.production:"
KEY_LEN="$(ssh -p "${DS723_PORT}" "${DS723_USER}@${DS723_HOST}" \
  "awk -F= '/^REGON_API_KEY=/{print length(\$2)}' '${DS723_ENV_FILE}'")"
if [[ "${KEY_LEN:-0}" -lt 10 ]]; then
  bad "REGON_API_KEY pusty lub za krótki (len=${KEY_LEN:-0})"
else
  ok "REGON_API_KEY ustawiony (len=${KEY_LEN})"
fi

echo "[preflight] frontend-react/dist na NAS:"
DIST_OK="$(ssh -p "${DS723_PORT}" "${DS723_USER}@${DS723_HOST}" \
  "test -f '${DS723_REPO}/frontend-react/dist/index.html' && echo yes || echo no")"
if [[ "${DIST_OK}" != "yes" ]]; then
  bad "brak ${DS723_REPO}/frontend-react/dist/index.html"
else
  ok "frontend dist obecny"
fi

echo
bash "${SCRIPT_DIR}/healthcheck.sh" || FAIL=1

if [[ "${FAIL}" -ne 0 ]]; then
  echo "[preflight] ZAKOŃCZONE Z BŁĘDAMI"
  exit 1
fi
echo "[preflight] GOTOWE"
