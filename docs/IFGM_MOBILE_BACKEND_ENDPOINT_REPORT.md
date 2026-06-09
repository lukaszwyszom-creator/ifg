# IFGM — raport: minimalny endpoint dashboard

**Data:** 2026-06-08

## Cel

`GET /api/v1/mobile/dashboard` — chroniony JWT, response zgodny z `mobile-expo/src/api/mobile.ts`.

## Zmiany

### `app/api/routers/mobile.py` (nowy / zminimalizowany)

- `APIRouter(prefix="/mobile")`
- `GET /dashboard` + alias `GET /dashboard/summary` (`include_in_schema=False`)
- Auth: `Depends(get_current_user)` — jak pozostałe chronione endpointy
- Response: `DashboardResponse` ze `app.schemas.mobile` (wszystkie pola wymagane przez frontend, wartości zerowe)
- Bez `MobileService` / bez zapytań do bazy (MVP pod deploy na DS723+)

### `app/main.py`

- Import `mobile_router` (L20)
- `application.include_router(mobile_router, prefix=settings.api_v1_prefix)` (L88)

### `mobile-expo/src/api/mobile.ts`

- Bez zmian — `GET /mobile/dashboard?period=YYYY-MM` (client dokleja `/api/v1`)

## Kontrakt response (frontend)

| Pole | Typ TS |
|------|--------|
| period | string |
| sales_net, purchase_net, vat_balance | string (Decimal JSON) |
| vat_label | `due` \| `refund` |
| debtors_*, creditors_*, unassigned_* | number / string |
| ksef_* | number / string / null |
| recent_purchase_invoices | array |

## Testy

```bash
# bez JWT — 401 (nie 404)
curl -i http://100.87.84.118:8000/api/v1/mobile/dashboard

# alias summary — 401
curl -i http://100.87.84.118:8000/api/v1/mobile/dashboard/summary

# z JWT — 200 + JSON
TOKEN=$(curl -s -X POST http://100.87.84.118:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"***"}' | jq -r .access_token)

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://100.87.84.118:8000/api/v1/mobile/dashboard?period=2026-06" | jq .
```

## Deploy DS723+

```bash
git pull origin production
docker compose -f docker/docker-compose.prod.yml build api
docker compose -f docker/docker-compose.prod.yml up -d api
```

## Ryzyko

| Ryzyko | Ocena |
|--------|-------|
| MVP zwraca same zera — dashboard pusty do czasu podpięcia `MobileService` | oczekiwane |
| Wymaga `app/schemas/mobile.py` w obrazie Docker | niskie (już w repo) |
| 404 bez rebuild kontenera | wysokie |
