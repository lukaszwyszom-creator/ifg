# GWO-IFG-KSEF-BUYER-ADDRESS-UI-0010 — FIX / DEPLOY / VERIFY

**Date:** 2026-09-23
**GWO:** GWO-0010 ETAP 7-8 (DEPLOY + SMOKE)
**Branch:** `production`

## STATUS (final)

| Field | Value |
|-------|-------|
| DEPLOY | PASS |
| DEPLOYED_SHA | `e6e5bc310d48b11e5fb9d18265e6d31844b4b550` (`e6e5bc3`) |
| ROLLBACK_SHA | `e0a53b0bf673f2243fca90d522edf999622224ae` (not used) |
| DS723_HEAD_MATCH | YES (`git rev-parse HEAD` == tip) |
| HEALTH | PASS (`{"status":"ok",...}`) |
| COMPOSE | api/db/worker healthy |
| UI_HASH | `index-CaH0FOv4.js` disk == `/ui/` served |
| DIST_STRINGS | PASS (see smoke) |
| SNAPSHOT_RO | YES city=`Prusicko` postal=`98-331` (column `buyer_snapshot_json`, invoice `c7643dfd-…`) |
| STALE_NGINX | `ifg-frontend-1` still Up 2 days on `:32768` with old `index-CvGj8pqP.js` — **canonical UI is `/ui` via API :8000** |
| SKIP_TESTS | 1 (local dirty tree; deploy continued with `yes`) |

## SHAs

| Field | Value |
|-------|-------|
| BASE_HEAD / ROLLBACK | `e0a53b0bf673f2243fca90d522edf999622224ae` |
| FEATURE_COMMIT | `8259a5491098ad0942c9da82e22e1fd0175323f0` |
| TIP / DEPLOYED | `e6e5bc310d48b11e5fb9d18265e6d31844b4b550` |
| origin/production @ deploy start | `e6e5bc3` (MATCH local HEAD) |

## ROOT_CAUSE (unchanged)

- Address editor existed but gated on `buyerInfo` only (hidden until lookup)
- Subtle CSS made section easy to miss
- KSeF message lacked path to Adres nabywcy
- Stale nginx `ifg-frontend:32768` lacks feature (API `/ui` has it)

## Deploy evidence

Command:

```bash
yes | SKIP_TESTS=1 bash scripts/deploy-ds723.sh
```

- Frontend build on Mac: `index-CaH0FOv4.js` + `index-0Q_2nEL1.css`
- Dist synced via tar/SSH; `git pull` on DS723 fast-forward `e0a53b0..e6e5bc3`
- `docker compose build api` (layers CACHED); containers healthy
- `alembic upgrade head` OK
- Script reported: `Deploy zakończony (commit: e6e5bc3)`

## Smoke (READ-ONLY)

### Dist strings (`frontend-react/dist` on DS723)

- `Adres nabywcy` — present in `index-CaH0FOv4.js`
- `ifgFocusBuyerAddress` / `Uzupełnij Adres nabywcy` — present
- `buyerAddressBlockIncomplete` — present (js + css)
- `REGON nie zwrócił pełnego adresu. Uzupełnij poniższe pola` — present

### `/ui/` hash match

- Disk: `index-CaH0FOv4.js`
- `curl http://127.0.0.1:8000/ui/` → same hash — **UI_HASH_MATCH=YES**
- Canonical URL: **`/ui` via API (127.0.0.1:8000)**

### Stale nginx frontend

- Container `ifg-frontend-1` (`ifg-frontend:latest`) Up 2 days, host port **32768**
- Serves old assets: `index-CvGj8pqP.js` / `index-BnFxgggD.css`
- Do **not** use `:32768` for verification of this GWO

### Optional API/DB RO

- Invoice `c7643dfd-cdb7-4913-8353-20bd16f98b8f`
- `buyer_snapshot_json.city=Prusicko`, `postal_code=98-331` — **no mutation**

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [x] DEPLOYED_TO_DS723
- [x] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Czy zatrzymać / przebudować stale `ifg-frontend` na `:32768`, żeby nie mylił operatorów (canonical pozostaje `/ui`)?

## Next

- Operator UX check on production `/ui`: Adres nabywcy visible before REGON; focus from KSeF incomplete message
- Optional: refresh or retire `ifg-frontend:32768`
