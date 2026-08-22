# Deploy — KSeF auth status 100 retry (DS723+)

**Data:** 2026-08-22  
**Commit:** `0048795561f236b06450b802021cbcd7383895d4` (`0048795`)  
**Workflow Guardian:** `ifg deploy run --yes --allow-dirty-build`  
**Raport Guardian:** `docs/guardian/IFG_DEPLOY_RUN_2026_08_22.md`

---

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Deploy LIVE COMPLETE (exit 0, blockers 0).
- Obraz API i worker: `ifg.git.commit=0048795561f2` (zgodny z remote HEAD).
- Health z kontenera: `status=ok`, `environment=production`.
- Kontenery: `ifg-api-1` / `ifg-worker-1` / `ifg-db-1` **healthy**; jeden worker (`python -m app.worker`).
- W obrazie workera potwierdzony kod: `_TRANSIENT_AUTH_STATUSES` z **100+450**, parser statusu, log retry, journal `RETRY`/`RESUME` w `PurchaseAuthService`.
- Brak błędów startowych KSeF w logach po recreate (worker: `Worker startuje…`; API: startup complete).
- Scheduler tick żywy po deployu (`last_attempt_at` aktualizowany).

⚠️ ZNANE PROBLEMY
- Ścieżka behawioralna **status 100 → RETRY → RESUME → sync** nie była wymuszana sztuczną synchronizacją (zgodnie z zakresem). Potwierdzenie przy najbliższej naturalnej sesji auto, jeśli KSeF zwróci 100.

❌ CO NIE DZIAŁA
- Brak blockerów po deployu.

---

## 1. WYNIK DEPLOYU

| Pole | Wartość |
|------|---------|
| Status | **LIVE COMPLETE** |
| Duration | ~703 s |
| Decision | `READY_WITH_OVERRIDE` (`--allow-dirty-build`) |
| Doctor | `READY_WITH_WARNINGS` |
| Rollback commit | `0048795` |
| Alembic | SKIPPED — head `p6q7r8s9t0u1` |
| Rebuild | `docker compose … build api worker` (poprzedni `e578465` → `0048795`) |
| Compose | recreate `ifg-api-1`, `ifg-worker-1` |

Pipeline: git pull → frontend build → dist sync → docker build api/worker → compose up → image verify → logs — wszystkie wymagane kroki EXECUTED.

## 2. IMAGE / COMMIT

| Komponent | Label `ifg.git.commit` |
|-----------|-------------------------|
| Remote HEAD | `0048795` |
| `ifg-api-1` | `0048795561f236b06450b802021cbcd7383895d4` |
| `ifg-worker-1` | `0048795561f236b06450b802021cbcd7383895d4` |

Commit message: `fix(ksef): bounded retry on auth redeem status 100 and 450`

## 3. HEALTH / RUNTIME

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

| Check | Wynik |
|-------|--------|
| API healthy | TAK |
| Worker healthy | TAK (`pid` live, cmd `python -m app.worker`) |
| DB healthy | TAK |
| Dual worker | NIE (tylko `ifg-worker-1`) |
| Startup KSeF errors | BRAK w tail logów po starcie |

## 4. WERYFIKACJA KODU W OBRAZIE (READ-ONLY)

Worker container:

| Probe | Wynik |
|-------|--------|
| `_TRANSIENT_AUTH_STATUSES` / 100 | TAK |
| frozenset 100, 450 | TAK |
| log `KSeF auth w toku (status` | TAK |
| parser transient status | TAK |
| `on_transient_retry` + journal RETRY/RESUME | TAK |

Sztucznego syncu **nie** uruchamiano.

## 5. OBSERWACJA PO DEPLOYU (NATURALNA SESJA)

Następny slot auto: **2026-08-23 08:00** Europe/Warsaw (cron `0 8,14,20 * * *`).

Jeśli pojawi się status 100, oczekiwany Monitor (ten sam `correlation_id` syncu):

1. `RETRY` / `WARNING` (`auth_pending_100`) — powtórzenia w limicie redeem  
2. `RESUME` / `SUCCESS` (`auth_ready`) — po udanym redeem  
3. dalszy `PURCHASE_SYNC_AUTO` / metadata / import — **bez** natychmiastowego `ERROR` na pierwszej próbie 100  

Gdy 100 nie wystąpi — redeem 200 jak zwykle (bez RETRY); to też jest poprawne.

## A. ROOT CAUSE
(wdrożone) Redeem failował natychmiast przy auth status 100; fix wdrożony na DS723+.

## B. ZMIENIONE PLIKI (ten raport)
- `docs/reports/2026-08-22_KSEF_AUTH_STATUS_100_RETRY_DEPLOY.md`
- Guardian: `docs/guardian/IFG_DEPLOY_RUN_2026_08_22.md` (+ zależne doctor/plan/evaluate)

Kod aplikacji: commit `0048795` (już na `origin/production`).

## C. DEPLOY
Wykonany przez Guardiana — LIVE COMPLETE.

## D. TESTY
Pre-deploy: 87 passed (auth/sync/retry). Post-deploy: health + image label + kod w kontenerze.

## E. NASTĘPNY KROK
Przy najbliższej naturalnej sesji (lub pierwszym wystąpieniu statusu 100) potwierdzić w Monitorze sekwencję RETRY → RESUME → sync; wtedy można podnieść RELEASE STATE do `PRODUCTION_VERIFIED`.

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [x] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

*(PRODUCTION_VERIFIED odłożone do potwierdzenia ścieżki 100 na naturalnej sesji; infrastruktura i kod w obrazie już PASS.)*

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-08-22_KSEF_AUTH_STATUS_100_RETRY_DEPLOY.md`
- `docs/guardian/IFG_DEPLOY_RUN_2026_08_22.md`
- (kontekst) `docs/reports/2026-08-22_KSEF_AUTH_STATUS_100_RETRY_FIX.md`
- (kontekst) `docs/reports/2026-08-22_KSEF_PURCHASE_SYNC_2026-08-21_INCIDENT_AUDIT.md`
