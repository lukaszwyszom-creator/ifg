# GUARDIAN POLICY ENGINE V1 REPORT

## CEL

Domknięcie Release Engine V1 przez dodanie minimalnego, jawnego Policy Engine dla `guardian release evaluate`, tak aby decyzja produkcyjna była oparta na regułach, a nie wyłącznie na score.

## ZAKRES DOSTARCZONY

- Dodana warstwa Policy Engine (`scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py`).
- Dodany jawny plik reguł:
  - `scripts/ifg_guardian/policies/ifg_production.yaml`
- `release evaluate`:
  - nadal zbiera fakty i score,
  - finalną decyzję ustala Policy Engine.
- Raport `release evaluate` rozszerzony o:
  - reguły, które zadziałały,
  - wymagane akcje,
  - `backup_required`,
  - `staging_required`,
  - `production_blocked`.
- Dodane `guardian release explain` (minimum):
  - `guardian release explain`
  - `guardian release explain --json`

## MINIMALNE REGUŁY V1 (ZAIMPLEMENTOWANE)

1. Jeśli są zmiany Alembic (`alembic/**`) → co najmniej `STAGING_ONLY`.
2. Jeśli migracja dotyka tabel krytycznych (`invoices`, `transmissions`, `warehouse_layers`, `payments`) → backup wymagany.
3. Jeśli test discovery nie przechodzi → `PRODUCTION_BLOCKED`.
4. Jeśli frontend changed i check build frontend FAIL/CRITICAL → `PRODUCTION_BLOCKED`.
5. Jeśli backend changed (`app/**` lub `alembic/**`) → akcja wymagana: rebuild `api/worker`.
6. Jeśli są untracked poza raportami:
   - podejrzane wzorce (`.env`, `credentials`, `secret`, `key`) → `PRODUCTION_BLOCKED`,
   - pozostałe → co najmniej warning.
7. Jeśli doctor ma FAIL → minimum `STAGING_ONLY`.
8. Jeśli doctor ma CRITICAL → `PRODUCTION_BLOCKED`.

## DECYZJA: SCORE VS POLICY

- Release Score pozostaje metryką pomocniczą.
- Finalna decyzja jest nadpisywana przez Policy Engine i reguły jawne z konfiguracji.

## KOMPATYBILNOŚĆ

- Brak zmian w deploy workflow.
- Brak zmian w `ifg.doctor`.
- Brak implementacji `release stage/approve/production` (poza zakresem V1).

## STATUS

🩷 STATUS KOŃCOWY

✅ Co działa
- Policy Engine działa jako osobna warstwa decyzyjna.
- Reguły są utrzymane w zewnętrznym pliku policy.
- `guardian release evaluate` pokazuje reguły i wymagane akcje.
- `guardian release explain` udostępnia szybki wgląd w aktywną politykę.

⚠️ Znane problemy
- `ifg_production.yaml` jest celowo minimalny; kolejne wersje powinny rozszerzyć klasyfikację untracked i mapowanie migracji do tabel.
- Heurystyka wykrywania „critical table touched” bazuje na nazwach plików/ścieżkach.

❌ Co nie działa
- Brak historii decyzji release.
- Brak workflow wykonawczych `stage/approve/production` (placeholdery zostają).

A. Root cause
- W V1 brakowało formalnej polityki decyzyjnej oddzielonej od scoringu.

B. Zmienione pliki
- `scripts/ifg_guardian/policies/ifg_production.yaml`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/models.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/stages.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/report.py`
- `scripts/ifg_guardian/modules/ifg_release_evaluate.py`
- `scripts/ifg_guardian/cli.py`
- `tests/unit/test_guardian_ifg_release_evaluate_workflow.py`

C. Deploy
- Nie wykonywano deployu.

D. Testy
- Uruchamiane po implementacji (wynik podany w odpowiedzi końcowej).

E. Następny krok
- Po tej wersji można wejść w wdrożenie KSeF Monitor i auto-sync 2x dziennie z kontrolą polityk przed produkcją.
