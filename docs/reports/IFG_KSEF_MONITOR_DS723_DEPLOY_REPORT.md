# IFG_KSEF_MONITOR_DS723_DEPLOY_REPORT

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Naprawiono przyczynę zatrzymania `dist sync` przez dodanie konfigurowalnego `remote_rsync_path`:
  - nowy parametr konfiguracji celu deploy: `DS723_REMOTE_RSYNC_PATH`,
  - dla DS723 ustawiono: `/bin/rsync`,
  - komenda Guardiana budowana jako:
    `rsync -av --rsync-path=/bin/rsync -e "ssh -p 32122" ...`.
- `guardian ifg deploy run --yes` wykonany do końca (LIVE COMPLETE):
  - `git pull` ✅
  - `frontend build` ✅
  - `artifact verify local` ✅
  - `dist sync` ✅
  - `artifact verify remote` ✅
  - `docker build api/worker` ✅
  - `compose up` ✅
  - `health check` ✅
  - `log verification` ✅
- Po deployu:
  - `/health` zwraca `200` i `environment=production`,
  - kontenery `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` działają.
- Frontend bundle na DS723 zawiera elementy Monitora:
  - `Monitor KSeF` (znaleziony),
  - `Tylko błędy i ostrzeżenia` (znaleziony).

⚠️ ZNANE PROBLEMY
- Część backendowa auto-sync zakupów nie jest aktywna w aktualnym obrazie API:
  - brak kluczy konfiguracyjnych auto-sync w runtime `Settings` (lista kluczy nie zawiera pól auto-sync),
  - w `.env.production` brak `KSEF_AUTO_SYNC_ENABLED` i `KSEF_AUTO_SYNC_CRON`.
- Schemat `transmissions` na produkcji jest częściowy względem pełnego modelu Monitora:
  - `operation_type` istnieje,
  - kolumna `severity` nie istnieje (zapytanie SQL zwraca błąd).
- Ręczna synchronizacja zakupów przez API wymaga autoryzacji:
  - `POST /api/v1/ksef/sync/purchases` bez tokenu zwraca `401 Unauthorized`.

❌ CO NIE DZIAŁA
- Nie potwierdzono produkcyjnie pełnego uruchomienia auto-sync 2x dziennie (brak aktywnej konfiguracji auto-sync w działającym backendzie).
- Nie wykonano end-to-end ręcznej synchronizacji zakupów z poziomu API/UI (brak tokenu operatora w sesji testowej).

A. ROOT CAUSE
- Pierwotna blokada deploy:
  - Guardian zatrzymywał się na `dist sync` z błędem rsync.
- Root cause:
  - domyślne wywołanie rsync bez jawnej ścieżki zdalnej binarki.
- Naprawa:
  - dodanie `remote_rsync_path` do konfiguracji DS723 i użycie go przy budowie komendy rsync.

B. ZMIENIONE PLIKI
- `scripts/ifg_guardian/core/deploy_config.py`
- `scripts/ifg_guardian/core/frontend_artifacts.py`
- `scripts/ds723.env`
- `tests/unit/test_guardian_frontend_artifacts.py`
- `docs/reports/IFG_KSEF_MONITOR_DS723_DEPLOY_REPORT.md`

C. DEPLOY
- Wykonano:
  - `python scripts/guardian.py ifg deploy run --yes`
- Wynik:
  - `LIVE COMPLETE` (workflow `2026-07-07T100025Z_ifg_deploy_run`)
- Dowody:
  - wszystkie wymagane kroki pipeline oznaczone jako `EXECUTED`,
  - `dist sync` zakończony `exit code: 0` po zmianie na `--rsync-path=/bin/rsync`.

D. TESTY
- Test jednostkowy po zmianie:
  - `PYTHONPATH=scripts pytest tests/unit/test_guardian_frontend_artifacts.py`
  - wynik: `10 passed`.
- Walidacja produkcyjna:
  - `GET /health` ✅
  - `docker compose ps` ✅
  - logi `api/worker` bez błędów startowych krytycznych ✅
  - UI bundle zawiera etykiety Monitora KSeF ✅
  - manual purchase sync bez tokenu: `401` (oczekiwane dla nieautoryzowanego wywołania) ⚠️

E. NASTĘPNY KROK
- Aby domknąć pełne wdrożenie „Monitor KSeF + auto-sync zakupów 2x dziennie”:
  1. dostarczyć na DS723 obraz backendu z aktywnymi polami auto-sync w `Settings`,
  2. ustawić w `.env.production`:
     - `KSEF_AUTO_SYNC_ENABLED=true`
     - `KSEF_AUTO_SYNC_CRON=0 8,14 * * *`
  3. wykonać autoryzowany test `POST /api/v1/ksef/sync/purchases`,
  4. potwierdzić wpisy dziennika KSeF dla synchronizacji zakupów.
