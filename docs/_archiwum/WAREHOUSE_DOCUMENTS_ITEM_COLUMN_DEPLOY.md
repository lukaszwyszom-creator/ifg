# Wdrożenie: kolumna „Towar” w Dokumentach magazynowych

**Data:** 2026-06-20

## Commit

```
feat(warehouse): show item names in documents list
```

## Pliki

- `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`
- `frontend-react/src/pages/warehouse/WarehousePage.module.css`
- `docs/WAREHOUSE_DOCUMENTS_ITEM_COLUMN_FIX.md`

## Zmiana

| Było | Jest |
|------|------|
| Kolumna „Opis / Powód” | Kolumna **„Towar”** |
| notes / issue_reason | nazwa towaru (+N, tooltip) |

Backend bez zmian — katalog z `GET /warehouse/items`.

## Build lokalny

```bash
cd frontend-react && npm run build
```

## Push

```bash
git push origin production
```

## Instrukcja DS723+

Ścieżka repo: `/volume1/docker/ifg_v2/ifg_standalone`

```bash
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH"
cd /volume1/docker/ifg_v2/ifg_standalone

# 1. Pobierz commit
git pull --ff-only origin production

# 2. Zbuduj frontend (dist bind-mount — wymagany rebuild)
cd frontend-react && npm ci && npm run build && cd ..

# 3. Restart api (serwuje /ui z dist; opcjonalnie worker bez zmian)
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  up -d --no-deps --force-recreate api

# 4. Smoke
curl -fsS http://127.0.0.1:8000/health
```

> **Uwaga:** Zmiana dotyczy wyłącznie frontendu (`dist/`). Restart `api` odświeża kontener serwujący statyczne pliki; `worker` nie wymaga recreate.

### Alternatywa (Mac mini → NAS)

Jeśli `npm` na DS723+ niedostępny — build na Mac mini i rsync dist (jak `scripts/deploy-ds723.sh`):

```bash
cd frontend-react && npm run build
tar czf - -C dist . | ssh -p 32122 zdalny_admin@ds723 \
  "mkdir -p /volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist && \
   tar xzf - -C /volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist"
```

## Weryfikacja po deploy

1. Magazyn → Dokumenty
2. Kolumna **„Towar”** (brak „Opis / Powód”)
3. Dokument z 1 pozycją → pełna nazwa
4. Dokument z wieloma → `Nazwa +N` + tooltip z listą
