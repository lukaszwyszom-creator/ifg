# KSeF purchase sync — manual vs incremental

## Problem

Ręczna synchronizacja z UI używała stanu `last_date_to` z `ksef_sync_states` i odpytywała wąskie okno (`last_date_to − overlap_days`), np. 2026-06-07 → 2026-06-09. Użytkownik oczekiwał pobrania brakujących faktur z szerszego okresu (np. cały maj/czerwiec).

## Rozwiązanie

Flaga `incremental: bool = False` w requestcie i serwisie.

| Tryb | `incremental` | Zakres dat (gdy brak `date_from`) |
|------|---------------|-----------------------------------|
| **Manual (UI, domyślnie)** | `false` | `dziś − settings.ksef_purchase_sync_days_back` (np. 90 dni) |
| **Manual + `force_full`** | `false` | `dziś − settings.ksef_purchase_sync_full_days` (365 dni) |
| **Manual + `date_from`/`date_to`** | dowolne | podany zakres |
| **Auto / job** | `true` | `last_date_to − overlap_days` → `dziś` (wymaga stanu sync) |

Priorytety w `resolve_purchase_sync_window` (bez zmian):

1. `date_from` podane → użyj go
2. `force_full=true` → pełny zakres historyczny
3. `incremental=true` + stan sync → okno inkrementalne
4. fallback → `days_back`

## Zmienione pliki

- `app/services/ksef_session_service.py` — parametr `incremental`, logika okna dat
- `app/api/routers/ksef_session.py` — `incremental: bool = False` w `KSeFPurchaseSyncRequest`
- `frontend-react/src/api/ksef.js` — jawne `incremental: false`, poprawka `force` → `force_full`

## Scenariusze testowe

```bash
# Manual bez body → ~90 dni wstecz (nie last_date_to)
curl -X POST .../ksef/sync/purchases -d '{}'

# Manual z zakresem
curl -X POST .../ksef/sync/purchases -d '{"date_from":"2026-05-01","date_to":"2026-06-09"}'

# Pełny import
curl -X POST .../ksef/sync/purchases -d '{"force_full": true}'

# Inkrementalny (auto-sync / job)
curl -X POST .../ksef/sync/purchases -d '{"incremental": true}'
```

## TODO

- Job/auto-sync (`KSeFSyncService` lub worker) powinien wywoływać sync z `incremental=True` — poza zakresem tej zmiany.
