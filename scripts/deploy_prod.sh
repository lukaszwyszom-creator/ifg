#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="docker/docker-compose.prod.yml"
ENV_FILE=".env.production"

cd "$ROOT_DIR"

echo "[deploy] Repo: $ROOT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[deploy][error] Missing $ENV_FILE in repo root"
  exit 1
fi

echo "[deploy] git pull --ff-only"
git pull --ff-only

echo "[deploy] frontend npm install"
cd frontend-react
npm install

echo "[deploy] frontend npm run build"
npm run build
cd "$ROOT_DIR"

echo "[deploy] docker compose up -d --build api worker"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build api worker

echo "[deploy] docker compose ps"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

check_status() {
  local url="$1"
  local expected_status="$2"
  local tmp_headers
  tmp_headers="$(mktemp)"

  curl -sS -D "$tmp_headers" -o /dev/null "$url"
  local status
  status="$(awk 'NR==1 {print $2}' "$tmp_headers")"
  rm -f "$tmp_headers"

  if [[ "$status" != "$expected_status" ]]; then
    echo "[deploy][error] $url returned status $status (expected $expected_status)"
    exit 1
  fi
  echo "[deploy][ok] $url status=$status"
}

check_html_200() {
  local url="$1"
  local tmp_headers
  tmp_headers="$(mktemp)"

  curl -sS -D "$tmp_headers" -o /dev/null "$url"
  local status
  status="$(awk 'NR==1 {print $2}' "$tmp_headers")"
  local content_type
  content_type="$(awk 'BEGIN{IGNORECASE=1} /^Content-Type:/ {print $0; exit}' "$tmp_headers")"
  rm -f "$tmp_headers"

  if [[ "$status" != "200" ]]; then
    echo "[deploy][error] $url returned status $status (expected 200)"
    exit 1
  fi
  if [[ "$content_type" != *"text/html"* ]]; then
    echo "[deploy][error] $url content-type is not text/html: ${content_type:-<missing>}"
    exit 1
  fi
  echo "[deploy][ok] $url status=200 content-type=${content_type#Content-Type: }"
}

check_asset_200() {
  local asset_path
  asset_path="$(grep -Eo '/ui/assets/[^" ]+' frontend-react/dist/index.html | head -n1 || true)"

  if [[ -z "$asset_path" ]]; then
    echo "[deploy][error] Could not find /ui/assets/... reference in frontend-react/dist/index.html"
    exit 1
  fi

  local tmp_headers
  tmp_headers="$(mktemp)"
  curl -sS -D "$tmp_headers" -o /dev/null "http://127.0.0.1:8000${asset_path}"
  local status
  status="$(awk 'NR==1 {print $2}' "$tmp_headers")"
  rm -f "$tmp_headers"

  if [[ "$status" != "200" ]]; then
    echo "[deploy][error] http://127.0.0.1:8000${asset_path} returned status $status (expected 200)"
    exit 1
  fi

  echo "[deploy][ok] http://127.0.0.1:8000${asset_path} status=200"
}

echo "[deploy] curl checks"
check_status "http://127.0.0.1:8000/health" "200"
check_status "http://127.0.0.1:8000/" "302"
check_html_200 "http://127.0.0.1:8000/ui/"
check_html_200 "http://127.0.0.1:8000/ui/invoices"
check_asset_200

echo "[deploy] DONE: production checks passed"
