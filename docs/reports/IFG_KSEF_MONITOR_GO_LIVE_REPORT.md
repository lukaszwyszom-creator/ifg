# IFG KSEF MONITOR GO LIVE REPORT

## STATUS

**WYMAGA POPRAWEK**

Deploy produkcyjny nie został domknięty, ponieważ `guardian ifg deploy run --yes` zakończył się błędem na etapie wykonania pipeline (`simulate_execution: failed 1 step(s)`).

## 1. Co zostało wdrożone

- Zweryfikowano w kodzie obecność Monitora KSeF:
  - `severity`,
  - `operation_type`,
  - `correlation_id`,
  - `metadata_json`,
  - liczniki (`Sukcesy/Ostrzeżenia/Błędy/W toku`),
  - filtr `Tylko błędy i ostrzeżenia`.
- Zweryfikowano auto-sync w backendzie:
  - obsługa `KSEF_AUTO_SYNC_ENABLED`,
  - obsługa `KSEF_AUTO_SYNC_CRON`,
  - domyślny cron: `0 8,14 * * *`,
  - logowanie zdarzeń lifecycle w `ksef_session_service`.

## 2. Backup

- Nie wykonano backupu produkcyjnego.
- Powód: pipeline deploy zakończył się błędem przed domknięciem etapów operacyjnych.

## 3. Build

- Build frontend lokalnie: **OK** (`npm run build`).
- Build obrazu `api/worker` w pipeline LIVE: **niepotwierdzony** (pipeline przerwany).

## 4. Deploy

- `guardian release evaluate --markdown`:
  - decyzja: `READY_WITH_WARNINGS`,
  - profile: `single_production`,
  - blockers: `None`.
- `guardian ifg deploy run --yes --markdown`:
  - wynik: **FAILED**,
  - stage: `simulate_execution`,
  - komunikat: `failed 1 step(s)`.

## 5. Migracje

- Migracje produkcyjne nie zostały potwierdzone jako wykonane.
- W planie dry-run krok `alembic upgrade` był oznaczony jako `Skipped — schema at head`.

## 6. Health

- Brak potwierdzonego health check po deployu (pipeline LIVE zakończony błędem).

## 7. Smoke tests

- Smoke testy po deployu nie zostały wykonane, bo deploy nie został domknięty.

## 8. Test sprzedaży

- Nie wykonano testowej wysyłki faktury sprzedaży na produkcji (brak zakończonego deployu).

## 9. Test UPO

- Nie wykonano walidacji odbioru UPO na produkcji (brak zakończonego deployu).

## 10. Test synchronizacji zakupów

- Nie wykonano ręcznej synchronizacji zakupów po deployu (brak zakończonego deployu).

## 11. Status schedulera

- W kodzie scheduler/konfiguracja istnieje (`KSEF_AUTO_SYNC_ENABLED`, `KSEF_AUTO_SYNC_CRON`).
- Potwierdzenie runtime produkcyjnego schedulera: **brak** (deploy nie został domknięty).

## 12. Status Monitora KSeF

- Implementacja w kodzie: **potwierdzona**.
- Walidacja produkcyjna po wdrożeniu: **niepotwierdzona** (deploy nie został domknięty).

## 13. Czy automatyczne pobieranie zakupów działa

- **Niepotwierdzone produkcyjnie** w tym przebiegu.

## 14. Czy IFG jest gotowy do codziennej pracy

- **WYMAGA POPRAWEK**.

## Dodatkowa diagnoza operacyjna

- Unifikacja gate działa poprawnie (deploy plan respektuje `READY_WITH_WARNINGS` i przechodzi do `ACTION_REQUIRED`).
- Brakujący element operacyjny: workflow `ifg deploy run` nie raportuje, który dokładnie krok pipeline zawiódł w LIVE (widzoczny jest tylko agregat: `failed 1 step(s)`), co utrudnia domknięcie incydentu wdrożeniowego bez ponownego ryzyka.
