#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# smoke_test.sh — KSeF Backend pre-deploy smoke test
#
# Użycie:
#   BASE_URL=http://localhost:8000 bash scripts/smoke_test.sh
#
# Wymagania: curl, jq
# ---------------------------------------------------------------------------
set -euo pipefail

# ERR trap – pokazuje numer linii i komendę, która spowodowała błąd
trap 'echo "  [ERR trap] linia $LINENO: $BASH_COMMAND" >&2' ERR

# ---------------------------------------------------------------------------
# Sprawdź zależności
# ---------------------------------------------------------------------------
if ! command -v jq &>/dev/null; then
    echo "BŁĄD: jq nie jest dostępne. Zainstaluj jq (brew install jq) i spróbuj ponownie."
    exit 1
fi

# ---------------------------------------------------------------------------
BASE_URL="${BASE_URL:-http://localhost:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"

PASS=0
FAIL=0
ERRORS=()
TOKEN=""
BUYER_ID=""
INVOICE_ID=""

# ---------------------------------------------------------------------------
# Helpery
# ---------------------------------------------------------------------------

check() {
    local label="$1"
    local actual="$2"
    local expected="$3"
    if [[ "$actual" == *"$expected"* ]]; then
        echo "  [PASS] $label"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $label  (got: $actual)"
        ERRORS+=("$label")
        FAIL=$((FAIL + 1))
    fi
}

warn() {
    echo "  [WARN] $1: $2"
}

# curl_req BODY_VAR STATUS_VAR [curl args...]
# Wykonuje żądanie curl z timeoutem; nigdy nie przerywa skryptu.
# Przy błędzie sieciowym status = "000".
curl_req() {
    local _body_var="$1"
    local _status_var="$2"
    shift 2
    local _tmp
    _tmp=$(mktemp)
    local _code
    _code=$(curl -s --max-time 5 -o "$_tmp" -w "%{http_code}" "$@") || _code="000"
    local _body
    _body=$(cat "$_tmp")
    rm -f "$_tmp"
    printf -v "$_body_var" '%s' "$_body"
    printf -v "$_status_var" '%s' "$_code"
}

# safe_jq BODY JQ_EXPR
# Parsuje JSON; przy błędzie wypisuje body na stderr i zwraca pusty string.
safe_jq() {
    local body="$1"
    local expr="$2"
    local result
    if ! result=$(echo "$body" | jq -r "$expr" 2>/dev/null); then
        echo "  [WARN] Niepoprawny JSON. Body: $body" >&2
        echo ""
        return 0
    fi
    echo "$result"
}

# ---------------------------------------------------------------------------
echo ""
echo "=== KSeF Backend Smoke Test ==="
echo "BASE_URL: $BASE_URL"
echo ""

# ---------------------------------------------------------------------------
# 1. Health (DB liveness)
# ---------------------------------------------------------------------------
echo "--- 1. Health (DB liveness) ---"
curl_req HEALTH_BODY HEALTH_STATUS "$BASE_URL/health"
check "GET /health → 200"        "$HEALTH_STATUS" "200"
check "GET /health → status:ok"  "$HEALTH_BODY"   '"status":"ok"'

# ---------------------------------------------------------------------------
# 2. Docs / OpenAPI
# ---------------------------------------------------------------------------
echo "--- 2. Docs ---"
curl_req _DOCS_BODY DOCS_STATUS "$BASE_URL/docs"
if [[ "$DOCS_STATUS" == "200" ]]; then
    echo "  [PASS] GET /docs → 200"
    PASS=$((PASS + 1))
else
    warn "GET /docs" "HTTP $DOCS_STATUS – endpoint może nie istnieć (niekrytyczne)"
fi

# ---------------------------------------------------------------------------
# 3. Login
# ---------------------------------------------------------------------------
echo "--- 3. Auth ---"
LOGIN_JSON="{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}"
curl_req LOGIN_BODY LOGIN_STATUS \
    -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "$LOGIN_JSON"
TOKEN=$(safe_jq "$LOGIN_BODY" '.access_token // empty')

if [[ -z "$TOKEN" ]]; then
    echo "  [FAIL] POST /auth/login → brak tokena. Pełna odpowiedź:"
    echo "         $LOGIN_BODY"
    ERRORS+=("POST /auth/login → token")
    FAIL=$((FAIL + 1))
else
    check "POST /auth/login → token" "$TOKEN" "eyJ"
fi

# ---------------------------------------------------------------------------
# 4. Invoice flow
# ---------------------------------------------------------------------------
echo "--- 4. Invoice flow ---"
if [[ -n "$TOKEN" ]]; then
    curl_req BUYER_BODY _BS "$BASE_URL/api/v1/contractors/by-nip/5260001572" \
        -H "Authorization: Bearer $TOKEN"
    BUYER_ID=$(safe_jq "$BUYER_BODY" '.id // empty')

    if [[ -z "$BUYER_ID" ]]; then
        echo "  [INFO] Kontrahent 5260001572 nie istnieje – tworzę..."
        curl_req SEED_BODY SEED_STATUS \
            -X POST "$BASE_URL/api/v1/contractors/" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"nip":"5260001572","name":"Test Buyer","city":"Warszawa","postal_code":"00-001","street":"Testowa","building_no":"1"}'
        BUYER_ID=$(safe_jq "$SEED_BODY" '.id // empty')
        if [[ -z "$BUYER_ID" ]]; then
            warn "Contractors/POST" "Nie udało się utworzyć kontrahenta. Body: $SEED_BODY"
        fi
    fi
else
    warn "Invoice flow" "Pominięto – brak tokena"
fi

if [[ -n "$TOKEN" && -n "$BUYER_ID" ]]; then
    INVOICE_PAYLOAD=$(cat <<EOF
{
  "buyer_id": "$BUYER_ID",
  "issue_date": "2026-04-05",
  "sale_date": "2026-04-05",
  "currency": "PLN",
  "items": [
    {
      "name": "Smoke test item",
      "quantity": "1",
      "unit": "szt",
      "unit_price_net": "100.00",
      "vat_rate": "23"
    }
  ]
}
EOF
)
    curl_req CREATE_BODY CREATE_STATUS \
        -X POST "$BASE_URL/api/v1/invoices/" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$INVOICE_PAYLOAD"
    INVOICE_ID=$(safe_jq "$CREATE_BODY" '.id // empty')
    check "POST /invoices → 201"        "$CREATE_STATUS" "201"
    check "POST /invoices → id present" "$INVOICE_ID"    "-"

    # 5. List invoices
    curl_req _LB LIST_STATUS \
        -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/invoices/"
    check "GET /invoices → 200" "$LIST_STATUS" "200"

    # 6. Mark as ready
    if [[ -n "$INVOICE_ID" ]]; then
        curl_req READY_BODY READY_STATUS \
            -X POST "$BASE_URL/api/v1/invoices/$INVOICE_ID/mark-ready" \
            -H "Authorization: Bearer $TOKEN"
        check "POST /invoices/{id}/mark-ready → 200"          "$READY_STATUS" "200"
        check "POST /invoices/{id}/mark-ready → number_local" "$READY_BODY"   "FV/"
    fi
fi

# ---------------------------------------------------------------------------
# 7. Payment CSV import
# ---------------------------------------------------------------------------
echo "--- 5. Payments ---"
if [[ -n "$TOKEN" ]]; then
    CSV_FILE=$(mktemp /tmp/smoke_XXXX.csv)
    printf 'transaction_date,amount,currency,title\n2026-04-05,123.00,PLN,Smoke test przelew\n' > "$CSV_FILE"
    curl_req _PB CSV_STATUS \
        -X POST "$BASE_URL/api/v1/payments/import" \
        -H "Authorization: Bearer $TOKEN" \
        -F "file=@$CSV_FILE;type=text/csv"
    rm -f "$CSV_FILE"
    check "POST /payments/import → 200" "$CSV_STATUS" "200"
else
    warn "Payments" "Pominięto – brak tokena"
fi

# ---------------------------------------------------------------------------
# 8. Contractor override
# ---------------------------------------------------------------------------
if [[ -n "$TOKEN" && -n "$BUYER_ID" ]]; then
    echo "--- 6. Contractor override ---"
    curl_req _OB OVR_STATUS \
        -X PATCH "$BASE_URL/api/v1/contractors/$BUYER_ID/override" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"name":"Smoke Override Name"}'
    check "PATCH /contractors/{id}/override → 200" "$OVR_STATUS" "200"
fi

# ---------------------------------------------------------------------------
# 9. Transmissions list
# ---------------------------------------------------------------------------
echo "--- 7. Transmissions ---"
if [[ -n "$TOKEN" ]]; then
    curl_req _TB TX_STATUS \
        -H "Authorization: Bearer $TOKEN" \
        "$BASE_URL/api/v1/transmissions/"
    check "GET /transmissions → 200" "$TX_STATUS" "200"
else
    warn "Transmissions" "Pominięto – brak tokena"
fi

# ---------------------------------------------------------------------------
# 10. Non-existent resource → 404
# ---------------------------------------------------------------------------
echo "--- 8. Error handling ---"
if [[ -n "$TOKEN" ]]; then
    curl_req _NB NOT_FOUND "$BASE_URL/api/v1/invoices/00000000-0000-0000-0000-000000000000" \
        -H "Authorization: Bearer $TOKEN"
    check "GET /invoices/non-existent → 404" "$NOT_FOUND" "404"
fi

# 11. Unauthorized → 401
curl_req _UB UNAUTH "$BASE_URL/api/v1/invoices/"
check "GET /invoices without token → 401" "$UNAUTH" "401"

# ---------------------------------------------------------------------------
echo ""
echo "=== WYNIK ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo "Nieudane testy:"
    for e in "${ERRORS[@]}"; do echo "  - $e"; done
    exit 1
else
    echo "Wszystkie OK"
    exit 0
fi
