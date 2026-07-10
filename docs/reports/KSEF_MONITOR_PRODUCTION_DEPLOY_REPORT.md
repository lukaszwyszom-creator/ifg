# KSEF MONITOR PRODUCTION DEPLOY REPORT

🩷 STATUS KOŃCOWY

✅ Co wdrożono
- Wykonano walidację gotowości wdrożenia przez `guardian release evaluate`.
- Potwierdzono, że kod Monitora KSeF zawiera wymagane typy operacji, severity, correlation_id/metadata oraz UI filtry/liczniki.
- Potwierdzono obecność konfiguracji auto-sync:
  - `KSEF_AUTO_SYNC_ENABLED`
  - `KSEF_AUTO_SYNC_CRON` (default `0 8,14 * * *`)
- Zweryfikowano lokalnie build frontendu i testy API transmisji.

⚠️ Znane problemy
- Produkcyjny deploy został zatrzymany przez istniejący workflow `ifg deploy run`.
- Przyczyna: deploy pipeline nadal blokuje na `ifg.release.plan`/`ifg.doctor` (risk=CRITICAL, doctor BLOCKED), mimo że `release evaluate` zwraca `READY_WITH_WARNINGS`.
- To jest realny brak operacyjny w integracji gate `release evaluate` -> `ifg deploy run`.

❌ Co nie działa
- Nie udało się przeprowadzić pełnego produkcyjnego pipeline (backup/build/deploy/migration/restart/health/smoke) ze względu na blokadę wewnątrz Guardiana.
- Brak możliwości wykonania testów produkcyjnych (sprzedaż/UPO/manual sync/scheduler live) bez zakończonego deployu.

## Migracje
- Migracja `transmissions` nie została wykonana na produkcji (deploy nie doszedł do etapu migracji).

## Backup
- Backup produkcyjny nie został wykonany, bo deploy zatrzymał się wcześniej na stage `blocker`.

## Build
- Lokalny build frontendu: OK (`npm run build` zakończone sukcesem).
- Rebuild produkcyjny `api/worker` nie został wykonany (zatrzymanie pipeline).

## Deploy
- `guardian release evaluate --markdown`: `READY_WITH_WARNINGS` (single_production).
- `guardian ifg deploy run --yes`: `FAILED` na stage `blocker: 2 blocker(s)`.
- Szczegóły z `.guardian/latest/ifg_deploy_run.json`:
  - blocker: `Doctor status is BLOCKED`
  - blocker: `Deployment risk is CRITICAL: Doctor status: BLOCKED`

## Health
- Brak post-deploy health check (deploy nie został wykonany).

## Smoke tests
- Brak smoke testów po deployu (deploy nie został wykonany).

## Test sprzedaży
- Nie wykonano na produkcji (brak deployu).

## Test UPO
- Nie wykonano na produkcji (brak deployu).

## Test synchronizacji zakupów
- Nie wykonano na produkcji (brak deployu).

## Status scheduler
- Konfiguracja w kodzie obecna (`KSEF_AUTO_SYNC_ENABLED`, `KSEF_AUTO_SYNC_CRON`).
- Walidacja runtime na produkcji nie została wykonana (brak deployu).

## Status Monitora KSeF
- Implementacja potwierdzona w kodzie:
  - operation types: SESSION_*, SALE_*, UPO_DOWNLOAD, PURCHASE_*, RETRY, RESUME, ERROR
  - severity enum i mapowanie UI
  - UI: liczniki + filtr "Tylko błędy i ostrzeżenia"
  - logging lifecycle w `ksef_session_service`
- Brak walidacji produkcyjnej po wdrożeniu (deploy zablokowany).

## Lista znanych problemów
1. Niespójność bramek Guardiana:
   - `release evaluate` dopuszcza deploy (`READY_WITH_WARNINGS`)
   - `ifg deploy run` blokuje z powodu `ifg.release.plan`/`doctor` (CRITICAL/BLOCKED)
2. Repo jest świadomie dirty (zakres wdrożenia niezamknięty commitowo), co podnosi warningi doctor.

## Ocena gotowości
- **WYMAGA POPRAWEK**

## Rzeczywisty brak operacyjny ujawniony podczas wdrożenia
- Guardian v1 ma konflikt semantyczny między warstwą `release evaluate` i `ifg deploy run`.
- Nie omijano blokady.
- Minimalna poprawka (do rozważenia po decyzji): zharmonizować źródło decyzji deploy gate tak, aby `ifg deploy run` respektował model `single_production` i wynik Policy Engine `release evaluate`.
