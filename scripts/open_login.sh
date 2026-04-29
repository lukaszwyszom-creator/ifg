#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend-react"
URL="http://127.0.0.1:3000/login"
HEALTH_URL="http://127.0.0.1:3000/login"
LOG_DIR="$ROOT_DIR/.logs"
LOG_FILE="$LOG_DIR/frontend-dev.log"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-60}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-1}"

mkdir -p "$LOG_DIR"

is_port_open() {
    lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1
}

is_login_ready() {
    local status
    status="$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || true)"
    [[ "$status" == "200" ]]
}

start_frontend_in_background() {
    echo "[open_login] Uruchamiam frontend dev server w tle..."
    (
        cd "$FRONTEND_DIR"
        nohup npm run dev >>"$LOG_FILE" 2>&1 &
    )
}

wait_for_login() {
    local started_at now elapsed
    started_at="$(date +%s)"

    while true; do
        if is_login_ready; then
            return 0
        fi

        now="$(date +%s)"
        elapsed="$((now - started_at))"
        if (( elapsed >= TIMEOUT_SECONDS )); then
            echo "[open_login] Timeout po ${TIMEOUT_SECONDS}s: $URL nie odpowiada jeszcze 200."
            echo "[open_login] Podgląd logu: tail -n 50 $LOG_FILE"
            return 1
        fi

        sleep "$POLL_INTERVAL_SECONDS"
    done
}

if is_port_open && is_login_ready; then
    echo "[open_login] Frontend już działa na porcie 3000."
else
    if ! is_port_open; then
        start_frontend_in_background
    else
        echo "[open_login] Port 3000 jest zajęty, ale /login jeszcze niegotowe. Czekam..."
    fi

    wait_for_login
fi

echo "[open_login] Login aktywny: $URL"
open "$URL"