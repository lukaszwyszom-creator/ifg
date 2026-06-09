# IFGM — raport naprawy HTTP 404 dashboard (DS723+)

**Data:** 2026-06-08  
**Host:** `100.87.84.118:8000` (Tailscale DS723+)

## Objaw

```bash
curl -i http://100.87.84.118:8000/api/v1/mobile/dashboard
# HTTP 404

curl -i http://100.87.84.118:8000/api/v1/mobile/dashboard/summary
# HTTP 404
```

`/docs` → 200, ale OpenAPI **nie zawiera** żadnej trasy `/mobile/*` (49 pathów vs 72 lokalnie z mobile).

## Przyczyna

Kontener API na DS723+ działa na **starszym obrazie** sprzed modułu IFGM mobile (`9223bd8`, `1ba0ee3`). Kod w repozytorium jest poprawny — brak redeploy/rebuild.

## Zmiany w kodzie

### `app/main.py`

- Rejestracja `mobile_router` przeniesiona tuż po `app = create_application()` — jawne podpięcie IFGM pod instancję `app` używaną przez uvicorn (`app.main:app`).

```python
app = create_application()
app.include_router(mobile_router, prefix=settings.api_v1_prefix)
```

### `app/api/routers/mobile.py`

- Alias `GET /mobile/dashboard/summary` → ten sam handler co `/mobile/dashboard` (kompatybilność ze starymi probe/curl).

### `mobile-expo/src/api/mobile.ts`

- Bez zmian — woła `GET /mobile/dashboard?period=YYYY-MM` (poprawna ścieżka względem `/api/v1`).

## Pełna ścieżka endpointu

`/api/v1` + `/mobile` + `/dashboard` = **`GET /api/v1/mobile/dashboard`**

## Wymagana akcja na DS723+

```bash
cd ~/projekty/ifg_standalone   # na hoście z dockerem
git pull origin production
docker compose -f docker/docker-compose.prod.yml build api
docker compose -f docker/docker-compose.prod.yml up -d api
```

Weryfikacja OpenAPI:

```bash
curl -s http://100.87.84.118:8000/openapi.json | jq '.paths | keys[] | select(contains("mobile"))'
```

Oczekiwane m.in. `/api/v1/mobile/dashboard`.

## Test curl

```bash
# bez tokena — oczekiwane 401 (NIE 404) po redeploy
curl -i http://100.87.84.118:8000/api/v1/mobile/dashboard

# z tokenem — oczekiwane 200
TOKEN=$(curl -s -X POST http://100.87.84.118:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"***"}' | jq -r .access_token)

curl -i -H "Authorization: Bearer $TOKEN" \
  "http://100.87.84.118:8000/api/v1/mobile/dashboard?period=2026-06"
```

## Ryzyko

| Ryzyko | Ocena |
|--------|-------|
| 404 bez rebuild obrazu Docker | wysokie — kod sam nie wystarczy |
| Podwójna rejestracja mobile (gdyby wrócić do include w `create_application` i na module) | niskie — tylko jedno miejsce |
| `/dashboard/summary` alias — duplikat w OpenAPI ukryty (`include_in_schema=False`) | minimalne |
